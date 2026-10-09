/* Extract successful S3 retrievals quickly from large retained log files.
 * Parse the fixed prefix and quoted request, then the status and byte fields.
 * Emit the same normalized records as the shell tool's portable awk parser.
 * Keep request IDs and event years for its global external-sort deduplication.
 * This helper performs no aggregation, networking, or source modifications.
 * Diagnostics distinguish accepted input lines from malformed successful lines.
 * The Makefile compiles it; count_access_logs.sh selects it explicitly.
 */
#define _POSIX_C_SOURCE 200809L
#include <ctype.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static char *token(char **cursor) {
    char *start = *cursor;
    while (*start && isspace((unsigned char)*start)) start++;
    if (!*start) return NULL;
    char *end = start;
    while (*end && !isspace((unsigned char)*end)) end++;
    if (*end) *end++ = '\0';
    *cursor = end;
    return start;
}

static int identifier(const char *text) {
    if (!*text) return 0;
    for (; *text; text++) {
        unsigned char c = (unsigned char)*text;
        if (!((c >= '0' && c <= '9') || (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z'))) return 0;
    }
    return 1;
}

int main(int argc, char **argv) {
    if (argc < 2) { fprintf(stderr, "usage: %s ACCESS_LOG...\n", argv[0]); return 2; }
    unsigned long long accepted = 0, malformed = 0;
    char *line = NULL;
    size_t capacity = 0;
    for (int file = 1; file < argc; file++) {
        FILE *input = fopen(argv[file], "r");
        if (!input) { perror(argv[file]); free(line); return 1; }
        while (getline(&line, &capacity, input) >= 0) {
            char *cursor = line, *prefix[9];
            int complete = 1;
            for (int i = 0; i < 9; i++) if (!(prefix[i] = token(&cursor))) { complete = 0; break; }
            if (!complete) continue;
            const char *operation = prefix[7], *key = prefix[8];
            if (strcmp(operation, "REST.GET.OBJECT") && strcmp(operation, "REST.COPY.PART_GET") && strcmp(operation, "WEBSITE.GET.OBJECT")) continue;
            char *quote = strchr(cursor, '"');
            if (!quote || !(quote = strchr(quote + 1, '"'))) continue;
            cursor = quote + 1;
            char *status = token(&cursor);
            if (!status || (strcmp(status, "200") && strcmp(status, "206"))) continue;
            if (!strcmp(key, "stats/digitalcorpora_configuration1.csv")) continue;
            char *error = token(&cursor), *bytes = token(&cursor);
            char *year = strrchr(prefix[2], '/');
            if (!error || !bytes || !year || strlen(++year) < 5 || year[4] != ':' || !identifier(prefix[6])) { malformed++; continue; }
            int valid = 1;
            for (int i = 0; i < 4; i++) if (year[i] < '0' || year[i] > '9') valid = 0;
            unsigned long long size = 0;
            if (strcmp(bytes, "-")) {
                for (const char *p = bytes; *p; p++) if (*p < '0' || *p > '9') valid = 0;
                errno = 0;
                char *end;
                size = strtoull(bytes, &end, 10);
                if (errno || *end) valid = 0;
            }
            if (!valid) { malformed++; continue; }
            const char *scope = !strncmp(key, "corpora/", 8) ? "corpora" : (!strncmp(key, "downloads/", 10) ? "tools" : "other");
            const char *m57_prefix = "corpora/scenarios/2009-m57-patents/";
            printf("%s %.4s %llu %s %d\n", prefix[6], year, size, scope, !strncmp(key, m57_prefix, strlen(m57_prefix)));
            accepted++;
        }
        if (ferror(input)) { perror(argv[file]); fclose(input); free(line); return 1; }
        fclose(input);
    }
    free(line);
    fprintf(stderr, "accepted_lines\t%llu\nmalformed_successful_lines\t%llu\n", accepted, malformed);
    return fflush(stdout) == EOF ? 1 : 0;
}
