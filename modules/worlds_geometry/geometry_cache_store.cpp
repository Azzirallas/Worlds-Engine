// Version-checked WGC1 disk cache; native exclusive temp files and flush-before-rename.
#include "geometry_cache_store.h"

#include <algorithm>
#include <array>
#include <cerrno>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <random>
#include <string>
#include <utility>
#include <system_error>

#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#include <share.h>
#include <sys/stat.h>
#include <windows.h>
#else
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>
#endif

namespace worlds_geometry {
namespace {
constexpr std::size_t kFileLimit = 24u * 1024u * 1024u;

bool read_bounded(const std::filesystem::path &path, std::vector<std::uint8_t> &bytes) {
    std::error_code ec;
    if (std::filesystem::is_symlink(std::filesystem::symlink_status(path,ec)) || ec ||
            !std::filesystem::is_regular_file(path,ec) || ec) { return false; }
    const auto length = std::filesystem::file_size(path,ec);
    if (ec || length == 0 || length > kFileLimit) { return false; }
    std::ifstream stream(path,std::ios::binary);
    if (!stream) { return false; }
    bytes.resize(static_cast<std::size_t>(length));
    stream.read(reinterpret_cast<char *>(bytes.data()),static_cast<std::streamsize>(length));
    return stream.gcount() == static_cast<std::streamsize>(length) && stream.peek() == std::char_traits<char>::eof();
}

std::string random_suffix() {
    std::random_device rd;
    // Exclusive create ensures correctness even when randomness is poor or processes collide.
    constexpr char hex[] = "0123456789abcdef";
    std::string out(24,'0');
    for (char &c : out) { c = hex[rd() & 0xfu]; }
    return out;
}

#ifdef _WIN32
enum class WriteResult { NOT_CREATED, WRITTEN, CREATED_FAILED };
WriteResult write_exclusive_synced(const std::filesystem::path &path, const std::vector<std::uint8_t> &bytes) {
    int fd = -1;
    if (_wsopen_s(&fd,path.c_str(),_O_CREAT|_O_EXCL|_O_WRONLY|_O_BINARY,
                  _SH_DENYRW,_S_IREAD|_S_IWRITE) != 0) { return WriteResult::NOT_CREATED; }
    bool okay = true;
    std::size_t offset = 0;
    while (okay && offset < bytes.size()) {
        const auto amount = static_cast<unsigned>(std::min<std::size_t>(bytes.size()-offset,1u<<20));
        const int written = _write(fd,bytes.data()+offset,amount);
        if (written <= 0) { okay=false; } else { offset += static_cast<std::size_t>(written); }
    }
    if (okay) { okay = _commit(fd) == 0; }
    if (_close(fd) != 0) { okay = false; }
    return okay ? WriteResult::WRITTEN : WriteResult::CREATED_FAILED;
}
bool replace_file(const std::filesystem::path &temp, const std::filesystem::path &path) {
    return MoveFileExW(temp.c_str(),path.c_str(),MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH) != 0;
}
#else
enum class WriteResult { NOT_CREATED, WRITTEN, CREATED_FAILED };
WriteResult write_exclusive_synced(const std::filesystem::path &path, const std::vector<std::uint8_t> &bytes) {
    const int fd = ::open(path.c_str(),O_WRONLY|O_CREAT|O_EXCL|O_CLOEXEC,0600);
    if (fd < 0) { return WriteResult::NOT_CREATED; }
    bool okay = true;
    std::size_t offset = 0;
    while (okay && offset < bytes.size()) {
        const ssize_t written = ::write(fd,bytes.data()+offset,bytes.size()-offset);
        if (written < 0 && errno == EINTR) { continue; }
        if (written <= 0) { okay=false; } else { offset += static_cast<std::size_t>(written); }
    }
    if (okay) { okay = ::fsync(fd) == 0; }
    if (::close(fd) != 0) { okay = false; }
    return okay ? WriteResult::WRITTEN : WriteResult::CREATED_FAILED;
}
bool replace_file(const std::filesystem::path &temp, const std::filesystem::path &path) {
    if (::rename(temp.c_str(),path.c_str()) != 0) { return false; }
    // Best-effort parent directory fsync for crash durability after the atomic rename.
    const auto parent = path.parent_path().empty() ? std::filesystem::path(".") : path.parent_path();
    const int fd = ::open(parent.c_str(),O_RDONLY|O_DIRECTORY|O_CLOEXEC);
    if (fd >= 0) { (void)::fsync(fd); (void)::close(fd); }
    return true;
}
#endif

bool publish_file(const std::filesystem::path &path, const std::vector<std::uint8_t> &bytes) {
    if (path.empty() || bytes.empty() || bytes.size() > kFileLimit) { return false; }
    std::error_code ec;
    const auto parent = path.parent_path().empty() ? std::filesystem::path(".") : path.parent_path();
    std::filesystem::create_directories(parent,ec);
    if (ec) { return false; }
    for (int i=0;i<8;++i) {
        auto temp = path;
        temp += ".tmp-" + random_suffix();
        const auto write_result = write_exclusive_synced(temp,bytes);
        if (write_result == WriteResult::NOT_CREATED) {
            // Never delete a file we did not create (exclusive temp-name collision).
            continue;
        }
        if (write_result == WriteResult::CREATED_FAILED) {
            std::filesystem::remove(temp,ec);
            return false;
        }
        const bool renamed = replace_file(temp,path);
        if (!renamed) { std::filesystem::remove(temp,ec); }
        return renamed;
    }
    return false;
}
} // namespace

GeometryStoreResult load_or_build_geometry_cache(
        const std::filesystem::path &cache_path, GeometryCacheSource source,
        const std::vector<std::uint8_t> &asset_bytes,
        const std::vector<std::uint8_t> &settings_bytes,
        const std::function<MeshletBuild()> &builder) {
    GeometryStoreResult result;
    if (cache_path.empty() || !stamp_geometry_cache_source(source,asset_bytes,settings_bytes)) {
        return result;
    }
    std::vector<std::uint8_t> stored;
    if (read_bounded(cache_path,stored)) {
        auto decoded = decode_geometry_cache(source,stored);
        if (decoded.status == GeometryCacheStatus::OK) {
            result.status = GeometryStoreStatus::HIT;
            result.build = std::move(decoded.build);
            return result;
        }
    }
    if (!builder) { result.status = GeometryStoreStatus::BUILD_FAILED; return result; }
    MeshletBuild built = builder();
    const auto encoded = encode_geometry_cache(source,built);
    if (encoded.status != GeometryCacheStatus::OK) {
        result.status = GeometryStoreStatus::BUILD_FAILED;
        return result;
    }
    result.build = std::move(built);
    result.status = publish_file(cache_path,encoded.bytes) ? GeometryStoreStatus::BUILT_STORED :
                                                           GeometryStoreStatus::BUILT_UNSTORED;
    return result;
}
} // namespace worlds_geometry
