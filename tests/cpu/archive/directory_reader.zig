extern "archive_directory_gpu" fn directory_input() callconv(.C) ?*const Inputs;
extern "archive_directory_gpu" fn enqueue_page(index: u32, offset: u64, size: u32) callconv(.C) u32;
extern "archive_directory_gpu" fn draw_pages() callconv(.C) u32;

// Readable prefix of a fixture file, its full size, and two requested logical pages.
const Inputs = extern struct { words: [*]const u64, bytes: u64, file_size: u64, first: u32, second: u32, bias: u64 };
fn physical(word: u64) u64 { return (word & 0x3ffffff) << 8; }
fn logical(word: u64) u64 { return (word >> 30) & 0x3fffff; }

fn validate(input: *const Inputs) u32 {
    if (input.bytes < 16) return 0;
    const words = input.words;
    if (@as(u32, @truncate(words[0])) != 0x35534452) return 0;
    const count = words[0] >> 32;
    if (count < 3 or count > (input.bytes - 16) / 8) return 0;
    const table = words + 2;
    var prev = table[0];
    const metadata = physical(prev);
    if (logical(prev) != 0 or ((prev >> 26) & 15) != 0 or metadata < 16 or count > (metadata - 16) / 8) return 0;
    var i: usize = 1;
    while (i < count) : (i += 1) {
        const next = table[i];
        if (logical(next) <= logical(prev) or physical(next) <= physical(prev)) return 0;
        prev = next;
    }
    if (physical(prev) > input.file_size or logical(prev) << 12 != (words[1] & 0xffffffffff)) return 0;
    return @intCast(count);
}

// The queue consumes one complete page per request. Only exact one-page zlib ranges qualify.
export fn locate(table: [*]const u64, count: usize, page: u32) callconv(.C) u32 {
    var low: usize = 0;
    var high: usize = count - 1;
    while (low + 1 < high) {
        const mid = low + (high - low) / 2;
        if (logical(table[mid]) <= page) low = mid else high = mid;
    }
    const word = table[low];
    const next = table[low + 1];
    if (logical(word) != page or logical(next) - logical(word) != 1 or (word >> 26 & 15) != 8) return 0;
    const span = physical(next) - physical(word);
    const padding = word >> 52;
    if (span <= padding or span - padding > 0xffffffff) return 0;
    return @intCast(low);
}

noinline fn queueRecord(table: [*]const u64, index: u32, bias: u64) bool {
    const word = table[index];
    const start = physical(word);
    const size: u32 = @intCast(physical(table[@as(usize, index) + 1]) - start - (word >> 52));
    const address = @addWithOverflow(start, bias);
    return address[1] == 0 and enqueue_page(index, address[0], size) == size;
}

pub fn main() u8 {
    const input = directory_input() orelse return 2;
    const count = validate(input);
    if (count == 0) return 3;
    const table = input.words + 2;
    const first = locate(table, count, input.first);
    const second = locate(table, count, input.second);
    if (first == 0 or second == 0) return 3;
    if (!queueRecord(table, first, input.bias) or !queueRecord(table, second, 0)) return 4;
    return @truncate(draw_pages());
}
