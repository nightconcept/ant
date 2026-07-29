#ifndef ANT_GC_STATS_H
#define ANT_GC_STATS_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include "types.h"

typedef enum {
  GC_STATS_MAJOR_AFTER_MINOR,
  GC_STATS_MAJOR_LIVE,
  GC_STATS_MAJOR_OVERFLOW,
  GC_STATS_MAJOR_POOL,
} gc_stats_major_cause_t;

typedef struct gc_policy_state {
  size_t nursery_threshold;
  uint32_t major_every_n;
  uint32_t live_growth_x256;
  uint32_t pool_growth_x256;
  uint32_t minor_surv_ewma;
  uint32_t major_recl_ewma;
  uint32_t remember_ewma;
  uint32_t promoted_ewma;
} gc_policy_state_t;

void gc_policy_state_get(gc_policy_state_t *out);

extern bool gc_stats_enabled;

void gc_stats_enable(bool enabled);
uint64_t gc_stats_begin(void);
void gc_stats_note_minor(
  ant_t *js, size_t young_before, size_t survivors, uint64_t start_ns
);
void gc_stats_note_major(ant_t *js, size_t freed, uint64_t start_ns);
void gc_stats_note_major_cause(gc_stats_major_cause_t cause);
void gc_stats_note_remember(size_t remember_set_len);

#endif
