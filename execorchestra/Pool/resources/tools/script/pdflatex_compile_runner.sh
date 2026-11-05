#!/bin/sh
# Deterministic LaTeX compilation inside the benchmark task container.
# This adapter intentionally uses only POSIX shell and pdflatex: official
# TerminalBench images provide TeX but do not necessarily provide Python.
set -eu

if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
  printf '%s\n' '{"status":"invalid","error":"expected source_path [output_dir]"}'
  exit 2
fi
source=$1
case "$source" in
  /app/*.tex|/tmp/*.tex|/tmp/*/*.tex|/tmp/*/*/*.tex) ;;
  *) printf '%s\n' '{"status":"invalid","error":"source_path_must_be_container_tex_file"}'; exit 2 ;;
esac
if [ ! -f "$source" ]; then
  printf '%s\n' '{"status":"missing","error":"source_file_missing"}'
  exit 2
fi
output_dir=${2:-${source%/*}}
if [ "$output_dir" != "${source%/*}" ] || [ ! -d "$output_dir" ]; then
  printf '%s\n' '{"status":"invalid","error":"output_dir_must_match_source_directory"}'
  exit 2
fi
if ! command -v pdflatex >/dev/null 2>&1; then
  printf '%s\n' '{"status":"failed","error":"pdflatex_not_available_in_task_image"}'
  exit 127
fi
base=${source##*/}
base=${base%.tex}
stdout_file=$(mktemp "${output_dir}/.sgar-pdflatex.stdout.XXXXXX")
stderr_file=$(mktemp "${output_dir}/.sgar-pdflatex.stderr.XXXXXX")
trap 'rm -f "$stdout_file" "$stderr_file"' EXIT HUP INT TERM
cd "$output_dir"
set +e
pdflatex -interaction=nonstopmode -halt-on-error -file-line-error -jobname="$base" "$base.tex" >"$stdout_file" 2>"$stderr_file"
code=$?
set -e
if [ "$code" -eq 0 ]; then status=ok; else status=failed; fi
pdf="${output_dir}/${base}.pdf"
log="${output_dir}/${base}.log"
produced='['
[ -f "$pdf" ] && produced="${produced}\"${pdf}\""
[ -f "$log" ] && { [ "$produced" != '[' ] && produced="${produced},"; produced="${produced}\"${log}\""; }
produced="${produced}]"
printf '{"status":"%s","source_path":"%s","output_path":"%s","produced_files":%s,"exit_code":%s}\n' "$status" "$source" "$pdf" "$produced" "$code"
exit "$code"
