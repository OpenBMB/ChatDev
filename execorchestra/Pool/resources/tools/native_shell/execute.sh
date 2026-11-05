#!/bin/sh
# The selected runtime owns isolation, cwd, time limits, and networking.
# A completed child failure is a declared business result, so a Controller
# can inspect the exit code and streams before deciding its next operation.
if [ "$#" -ne 1 ]; then
    printf '%s\n' 'Expected one POSIX shell program argument.' >&2
    exit 2
fi
capture_dir=$(mktemp -d) || exit 1
trap 'rm -rf -- "$capture_dir"' 0
trap 'exit 130' HUP INT TERM
sh -c "$1" >"$capture_dir/stdout" 2>"$capture_dir/stderr"
child_status=$?

# Encode bytes without shell command substitution on the content: that would
# strip trailing newlines. Control bytes are JSON escaped, valid UTF-8 is
# retained, and invalid non-ASCII bytes receive an explicit JSON projection.
json_text() {
    # Keep valid UTF-8 byte-for-byte.  Escape each invalid non-ASCII byte as a
    # JSON Unicode code point so arbitrary command output cannot corrupt the
    # UTF-8 JSON envelope returned to the runtime.
    od -An -v -tu1 "$1" | LC_ALL=C awk '
        # Only the current od row and up to three UTF-8 lookahead bytes
        # are retained. A long command stream must not become an AWK array
        # containing one heap entry for every byte.
        function emit(final, i, b, width, j, left) {
            i = 1
            while (i <= count && (final || count - i >= 3)) {
                b = bytes[i]
                if (b == 34) { printf "\\\""; i++; continue }
                if (b == 92) { printf "\\\\"; i++; continue }
                if (b < 32) { printf "\\u%04x", b; i++; continue }
                if (b < 128) { printf "%c", b; i++; continue }

                width = 0
                if (b >= 194 && b <= 223 && i + 1 <= count &&
                    bytes[i + 1] >= 128 && bytes[i + 1] <= 191) {
                    width = 2
                } else if (b == 224 && i + 2 <= count &&
                           bytes[i + 1] >= 160 && bytes[i + 1] <= 191 &&
                           bytes[i + 2] >= 128 && bytes[i + 2] <= 191) {
                    width = 3
                } else if (((b >= 225 && b <= 236) || (b >= 238 && b <= 239)) &&
                           i + 2 <= count &&
                           bytes[i + 1] >= 128 && bytes[i + 1] <= 191 &&
                           bytes[i + 2] >= 128 && bytes[i + 2] <= 191) {
                    width = 3
                } else if (b == 237 && i + 2 <= count &&
                           bytes[i + 1] >= 128 && bytes[i + 1] <= 159 &&
                           bytes[i + 2] >= 128 && bytes[i + 2] <= 191) {
                    width = 3
                } else if (b == 240 && i + 3 <= count &&
                           bytes[i + 1] >= 144 && bytes[i + 1] <= 191 &&
                           bytes[i + 2] >= 128 && bytes[i + 2] <= 191 &&
                           bytes[i + 3] >= 128 && bytes[i + 3] <= 191) {
                    width = 4
                } else if (b >= 241 && b <= 243 && i + 3 <= count &&
                           bytes[i + 1] >= 128 && bytes[i + 1] <= 191 &&
                           bytes[i + 2] >= 128 && bytes[i + 2] <= 191 &&
                           bytes[i + 3] >= 128 && bytes[i + 3] <= 191) {
                    width = 4
                } else if (b == 244 && i + 3 <= count &&
                           bytes[i + 1] >= 128 && bytes[i + 1] <= 143 &&
                           bytes[i + 2] >= 128 && bytes[i + 2] <= 191 &&
                           bytes[i + 3] >= 128 && bytes[i + 3] <= 191) {
                    width = 4
                }
                if (width > 0) {
                    for (j = 0; j < width; j++) printf "%c", bytes[i + j]
                    i += width
                } else {
                    printf "\\u00%02x", b
                    i++
                }
            }
            left = count - i + 1
            for (j = 1; j <= left; j++) bytes[j] = bytes[i + j - 1]
            for (j = left + 1; j <= count; j++) delete bytes[j]
            count = left
        }
        BEGIN { printf "\"" }
        {
            for (column = 1; column <= NF; column++) bytes[++count] = $column + 0
            emit(0)
        }
        END { emit(1); printf "\"" }
    '
}

if [ "$child_status" -eq 0 ]; then
    result_status=success
else
    result_status=error
fi
printf '{"status":"%s","exit_code":%s,"stdout":' "$result_status" "$child_status"
json_text "$capture_dir/stdout" || exit 1
printf ',"stderr":'
json_text "$capture_dir/stderr" || exit 1
printf '}\n'
