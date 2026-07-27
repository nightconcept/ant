#ifndef SILVER_VM_H
#define SILVER_VM_H

#include "types.h"

typedef struct sv_vm sv_vm_t;
typedef struct sv_func sv_func_t;
size_t os_thread_stack_size(void);

typedef enum {
  SV_VM_MAIN,
  SV_VM_ASYNC,
} sv_vm_kind_t;

extern int sv_user_stack_size_kb;
sv_vm_t *sv_vm_create(ant_t *js, sv_vm_kind_t kind);
sv_vm_t *sv_vm_create_sized(ant_t *js, int stack_size, int max_frames);

void sv_vm_destroy(sv_vm_t *vm);
void sv_vm_limits(sv_vm_kind_t kind, int *out_stack_size, int *out_max_frames);

/* Ensure the VM can hold `slots` operands / `count` frames; grows if needed. */
bool sv_vm_reserve_stack(sv_vm_t *vm, int slots);
bool sv_vm_reserve_frames(sv_vm_t *vm, int count);
bool sv_vm_reserve_handlers(sv_vm_t *vm, int count);

/* Upper bound on the operand slots one activation of a function can hold. */
int sv_func_max_stack_bound(const uint8_t *code, int code_len, int max_locals);

void sv_vm_visit_frame_funcs(sv_vm_t *vm, void (*visitor)(void *, sv_func_t *), void *ctx);
void sv_disasm(ant_t *js, sv_func_t *func, const char *label);

ant_value_t sv_execute_frame(
  sv_vm_t *vm, sv_func_t *func,
  ant_value_t this_val, ant_value_t super_val,
  ant_value_t *args, int argc
);

ant_value_t sv_execute_entry(
  sv_vm_t *vm, sv_func_t *func,
  ant_value_t this_val,
  ant_value_t *args, int argc
);

ant_value_t sv_execute_entry_tla(
  ant_t *js, sv_func_t *func, 
  ant_value_t this_val
);

ant_value_t sv_resume_suspended(sv_vm_t *vm);

#endif
