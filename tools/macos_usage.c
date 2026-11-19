/* Snapshot cumulative process counters from the macOS SDK. */
#include <inttypes.h>
#include <libproc.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/resource.h>

int main(int argc, char **argv) {
    if (argc != 2) {
        return 2;
    }
    struct rusage_info_v6 usage = {0};
    if (proc_pid_rusage(atoi(argv[1]), RUSAGE_INFO_V6, (rusage_info_t *)&usage) != 0) {
        return 1;
    }
    printf("{\"interrupt_wakeups\":%" PRIu64 ",\"package_wakeups\":%" PRIu64
           ",\"rss_bytes\":%" PRIu64 ",\"energy_nj\":%" PRIu64 "}\n",
           usage.ri_interrupt_wkups, usage.ri_pkg_idle_wkups,
           usage.ri_resident_size, usage.ri_energy_nj);
    return 0;
}
