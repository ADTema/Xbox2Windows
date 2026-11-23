#pragma once

struct ArchiveTexture {
    unsigned char rgba[4][4][4];
};

// The caller owns the pixels through the call. Return zero on success.
int consume_archive_texture(const ArchiveTexture& texture);
