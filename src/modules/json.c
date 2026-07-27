#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <math.h>
#include <yyjson.h>
#include <uthash.h>

#include "gc/roots.h"
#include "numbers.h"
#include "utf8.h"
#include "errors.h"
#include "internal.h"

#include "silver/engine.h"
#include "modules/json.h"
#include "modules/symbol.h"

typedef struct {
  const char *key;
  size_t key_len;
  ant_offset_t prop_off;
  UT_hash_handle hh;
} json_key_entry_t;

static void json_key_hash_free(json_key_entry_t **hash) {
  json_key_entry_t *entry, *tmp;
  HASH_ITER(hh, *hash, entry, tmp) {
    HASH_DEL(*hash, entry);
    free(entry);
  }
}

static inline bool json_value_needs_temp_root(ant_value_t value) {
  if (value <= NANBOX_PREFIX) return false;
  
  static const uint32_t mask =
    (1u << T_STR) | (1u << T_OBJ) | (1u << T_ARR) | (1u << T_FUNC) |
    (1u << T_PROMISE) | (1u << T_GENERATOR) | (1u << T_SYMBOL) | (1u << T_BIGINT);
    
  uint8_t t = vtype(value);
  return t < 32 && (mask >> t) & 1;
}

static inline bool json_temp_pin(gc_temp_root_scope_t *roots, ant_value_t value) {
  if (!json_value_needs_temp_root(value)) return true;
  return gc_temp_root_handle_valid(gc_temp_root_add(roots, value));
}

static inline ant_value_t json_parse_oom(ant_t *js) {
  return js_mkerr(js, "JSON.parse() failed: out of memory");
}

static inline ant_value_t json_stringify_oom(ant_t *js) {
  return js_mkerr(js, "JSON.stringify() failed: out of memory");
}

/* Duplicate-key detection is a linear scan of already-placed keys for objects
   up to this size; larger objects pay for a hash table instead. */
#define JSON_INLINE_DUP_KEYS 16

typedef struct {
  const char *key;
  size_t key_len;
  ant_offset_t prop_off;
} json_seen_key_t;

static ant_value_t yyjson_to_jsval(ant_t *js, yyjson_val *val) {
  if (!val) return js_mkundef();

  switch (yyjson_get_type(val)) {
  case YYJSON_TYPE_NULL: return js_mknull();
  case YYJSON_TYPE_BOOL: return js_bool(yyjson_get_bool(val));

  case YYJSON_TYPE_STR:
    return js_mkstr(js, yyjson_get_str(val), yyjson_get_len(val));

  case YYJSON_TYPE_NUM: {
    if (yyjson_is_sint(val)) return js_mknum((double)yyjson_get_sint(val));
    if (yyjson_is_uint(val)) return js_mknum((double)yyjson_get_uint(val));
    return js_mknum(yyjson_get_real(val));
  }

  case YYJSON_TYPE_ARR: {
    GC_ROOT_SAVE(root_mark, js);

    ant_value_t arr = js_mkarr(js);
    if (is_err(arr)) return arr;
    GC_ROOT_PIN(js, arr);

    /* Pinned by address so the freshly built element survives js_arr_push. */
    ant_value_t elem = js_mkundef();
    GC_ROOT_PIN(js, elem);

    size_t idx, max;
    yyjson_val *item;
    ant_value_t result = arr;

    yyjson_arr_foreach(val, idx, max, item) {
      elem = yyjson_to_jsval(js, item);
      if (is_err(elem)) {
        result = elem;
        break;
      }
      js_arr_push(js, arr, elem);
    }

    GC_ROOT_RESTORE(js, root_mark);
    return result;
  }

  case YYJSON_TYPE_OBJ: {
    GC_ROOT_SAVE(root_mark, js);

    ant_value_t obj = js_newobj(js);
    if (is_err(obj)) return obj;
    GC_ROOT_PIN(js, obj);

    ant_value_t v = js_mkundef();
    GC_ROOT_PIN(js, v);

    json_seen_key_t seen[JSON_INLINE_DUP_KEYS];
    size_t seen_count = 0;

    json_key_entry_t *hash = NULL, *entry;
    bool use_hash = yyjson_obj_size(val) > JSON_INLINE_DUP_KEYS;

    size_t idx, max;
    yyjson_val *key, *item;
    ant_value_t result = obj;

    yyjson_obj_foreach(val, idx, max, key, item) {
      const char *k = yyjson_get_str(key);
      size_t klen = yyjson_get_len(key);

      v = yyjson_to_jsval(js, item);
      if (is_err(v)) {
        result = v;
        break;
      }

      ant_offset_t dup_off = 0;

      if (use_hash) {
        HASH_FIND(hh, hash, k, klen, entry);
        if (entry) dup_off = entry->prop_off;
      } else {
        for (size_t i = 0; i < seen_count; i++) {
          if (seen[i].key_len == klen && memcmp(seen[i].key, k, klen) == 0) {
            dup_off = seen[i].prop_off;
            break;
          }
        }
      }

      if (dup_off != 0) {
        js_saveval(js, dup_off, v);
        continue;
      }

      ant_offset_t off = js_mkprop_fast_off(js, obj, k, klen, v);
      if (off == 0) {
        result = json_parse_oom(js);
        break;
      }

      if (!use_hash) {
        seen[seen_count].key = k;
        seen[seen_count].key_len = klen;
        seen[seen_count].prop_off = off;
        seen_count++;
        continue;
      }

      entry = malloc(sizeof(json_key_entry_t));
      if (!entry) {
        result = json_parse_oom(js);
        break;
      }

      entry->key = k; entry->key_len = klen; entry->prop_off = off;
      HASH_ADD_KEYPTR(hh, hash, entry->key, entry->key_len, entry);
    }

    json_key_hash_free(&hash);
    GC_ROOT_RESTORE(js, root_mark);
    return result;
  }

  default: return js_mkundef(); }
}

/* Growable byte buffer that JSON.stringify serializes straight into, so no
   intermediate document tree is materialized for the value graph. */
typedef struct {
  char *buf;
  size_t len;
  size_t cap;
  bool oom;
} json_out_t;

typedef struct {
  ant_t *js;
  ant_value_t *stack;
  ant_value_t replacer_func;
  ant_value_t replacer_arr;
  ant_value_t error;
  ant_value_t holder;
  ant_value_t cycle_start;

  gc_temp_root_scope_t temp_roots;
  gc_temp_root_handle_t error_handle;
  gc_temp_root_handle_t holder_handle;

  json_out_t out;
  int depth;
  size_t gap_len;
  char gap[48];

  int stack_size;
  int stack_cap;
  int replacer_arr_len;
  int has_cycle;
  char cycle_key[128];
} json_cycle_ctx;

static bool json_out_reserve(json_out_t *out, size_t extra) {
  size_t need = out->len + extra + 1;
  if (need <= out->cap) return true;

  size_t next = out->cap ? out->cap : 256;
  while (next < need) next *= 2;

  char *tmp = realloc(out->buf, next);
  if (!tmp) {
    out->oom = true;
    return false;
  }

  out->buf = tmp;
  out->cap = next;
  return true;
}

static inline void json_out_write(json_out_t *out, const char *src, size_t len) {
  if (!json_out_reserve(out, len)) return;
  memcpy(out->buf + out->len, src, len);
  out->len += len;
}

static inline void json_out_char(json_out_t *out, char ch) {
  if (!json_out_reserve(out, 1)) return;
  out->buf[out->len++] = ch;
}

static inline bool json_has_abort(json_cycle_ctx *ctx) {
  return ctx->has_cycle || ctx->out.oom || vtype(ctx->error) != T_UNDEF;
}

static inline ant_value_t json_normalize_error(ant_value_t value) {
  if (is_err(value) && vdata(value) != 0) return js_as_obj(value);
  return value;
}

static void json_set_error(json_cycle_ctx *ctx, ant_value_t value) {
  ctx->error = value;
  gc_temp_root_set(ctx->error_handle, value);
}

static inline bool json_ctx_pin_value(json_cycle_ctx *ctx, ant_value_t value) {
  if (json_temp_pin(&ctx->temp_roots, value)) return true;
  json_set_error(ctx, json_stringify_oom(ctx->js));
  return false;
}

static inline void json_set_holder(json_cycle_ctx *ctx, ant_value_t value) {
  ctx->holder = value;
  gc_temp_root_set(ctx->holder_handle, value);
}

static void json_capture_error(json_cycle_ctx *ctx, ant_value_t value) {
  if (vtype(ctx->error) != T_UNDEF) return;
  if (ctx->js->thrown_exists) {
    json_set_error(ctx, ctx->js->thrown_value);
    ctx->js->thrown_exists = false;
    ctx->js->thrown_value = js_mkundef();
    return;
  }
  json_set_error(ctx, json_normalize_error(value));
}

static void json_write_string(ant_t *js, json_cycle_ctx *ctx, ant_value_t value) {
  size_t byte_len = 0;
  char *str = js_getstr(js, value, &byte_len);
  json_out_t *out = &ctx->out;

  if (!utf8_json_quote_into(&out->buf, &out->len, &out->cap, str, byte_len)) out->oom = true;
}

static void json_write_number(json_cycle_ctx *ctx, double num) {
  char buf[64];

  if (!isfinite(num)) {
    json_out_write(&ctx->out, "null", 4);
    return;
  }

  if (num >= INT32_MIN && num <= INT32_MAX && num == (double)(int32_t)num) {
    int32_t ival = (int32_t)num;
    size_t len;
    if (ival < 0) {
      buf[0] = '-';
      len = 1 + uint_to_str(buf + 1, sizeof(buf) - 1, (uint64_t)(-(int64_t)ival));
    } else {
      len = uint_to_str(buf, sizeof(buf), (uint64_t)ival);
    }
    json_out_write(&ctx->out, buf, len);
    return;
  }

  size_t len = ant_number_to_shortest(num, buf, sizeof(buf));
  if (len == 0 || len >= sizeof(buf)) {
    json_out_write(&ctx->out, "null", 4);
    return;
  }

  json_out_write(&ctx->out, buf, len);
}

/* Emits the newline + indentation the `space` argument asks for. */
static void json_write_indent(json_cycle_ctx *ctx, int depth) {
  if (!ctx->gap_len) return;
  json_out_char(&ctx->out, '\n');
  for (int i = 0; i < depth; i++) json_out_write(&ctx->out, ctx->gap, ctx->gap_len);
}

static int json_cycle_check(json_cycle_ctx *ctx, ant_value_t val, const char *key) {
  for (int i = 0; i < ctx->stack_size; i++) if (ctx->stack[i] == val) {
    ctx->has_cycle = 1;
    ctx->cycle_start = val;
    snprintf(ctx->cycle_key, sizeof(ctx->cycle_key), "%s", key ? key : "");
    return 1;
  }
  return 0;
}

static ant_value_t json_cycle_error(ant_t *js, const json_cycle_ctx *ctx) {
  const char *ctor = ctx->cycle_start == js->global ? "global" : "Object";
  char message[384];
  snprintf(
    message, sizeof(message),
    "Converting circular structure to JSON\n"
    "    --> starting at object with constructor '%s'\n"
    "    --- property '%s' closes the circle",
    ctor,
    ctx->cycle_key
  );
  return js_mkerr_typed(js, JS_ERR_TYPE, "%s", message);
}

static void json_cycle_push(json_cycle_ctx *ctx, ant_value_t val) {
  if (ctx->stack_size >= ctx->stack_cap) {
    ctx->stack_cap = ctx->stack_cap ? ctx->stack_cap * 2 : 16;
    ctx->stack = realloc(ctx->stack, ctx->stack_cap * sizeof(ant_value_t));
  }
  ctx->stack[ctx->stack_size++] = val;
}

static inline void json_cycle_pop(json_cycle_ctx *ctx) {
  if (ctx->stack_size > 0) ctx->stack_size--;
}

static inline int key_matches(const char *a, size_t a_len, const char *b, size_t b_len) {
  return a_len == b_len && memcmp(a, b, a_len) == 0;
}

/* SerializeJSONObject uses EnumerableOwnPropertyNames, so own enumerable string
   keys only - no prototype chain, and no dedupe set to allocate. */
static inline ant_value_t json_snapshot_keys(ant_t *js, ant_value_t value) {
  if (!is_special_object(value)) return js_mkarr(js);
  /* A proxy's keys come from its ownKeys trap, which only the for-in entry
     point reaches from here. */
  if (is_proxy(value)) return js_for_in_keys(js, value);
  return js_own_property_keys(js, value, false, true);
}

static int is_key_in_replacer_arr(ant_t *js, json_cycle_ctx *ctx, const char *key, size_t key_len) {
  if (!is_special_object(ctx->replacer_arr)) return 1;
  
  for (int i = 0; i < ctx->replacer_arr_len; i++) {
  char idxstr[32];
  snprintf(idxstr, sizeof(idxstr), "%d", i);
  
  ant_value_t item = js_get(js, ctx->replacer_arr, idxstr);
  int type = vtype(item);
  
  if (type == T_STR) {
    size_t item_len;
    char *item_str = js_getstr(js, item, &item_len);
    if (key_matches(item_str, item_len, key, key_len)) return 1;
  } else if (type == T_NUM) {
    char numstr[32];
    snprintf(numstr, sizeof(numstr), "%.0f", js_getnum(item));
    if (key_matches(numstr, strlen(numstr), key, key_len)) return 1;
  }}
  
  return 0;
}

/* JSON_WRITE_SKIP means the value produces no output at all (an undefined,
   function or symbol property), which the caller must undo the key for. */
typedef enum {
  JSON_WRITE_OK,
  JSON_WRITE_SKIP,
  JSON_WRITE_ABORT,
} json_write_res;

static json_write_res json_write_with_key(
  ant_t *js, const char *key, ant_value_t val, json_cycle_ctx *ctx, int in_array
);

static ant_value_t apply_reviver(
  ant_t *js, ant_value_t holder,
  const char *key, ant_value_t reviver,
  gc_temp_root_scope_t *roots
);

static ant_value_t json_apply_tojson(
  ant_t *js,
  const char *key,
  ant_value_t val,
  json_cycle_ctx *ctx
) {
  if (!is_special_object(val)) return val;

  /* js_get only sees own properties, so inherited toJSON (Date's, above all)
     needs the prototype-walking lookup. lkp_proto rejects the common
     no-toJSON-anywhere case without materializing a value. */
  if (!is_proxy(val) && lkp_proto(js, val, "toJSON", 6) == 0) return val;
  ant_value_t toJSON = js_getprop_fallback(js, val, "toJSON");

  if (is_err(toJSON)) {
    json_capture_error(ctx, toJSON);
    return js_mkundef();
  }

  if (!is_callable(toJSON)) return val;
  ant_value_t key_arg = js_mkstr(js, key, strlen(key));
  if (is_err(key_arg)) {
    json_capture_error(ctx, key_arg);
    return js_mkundef();
  }
  
  if (!json_ctx_pin_value(ctx, key_arg)) return js_mkundef();
  ant_value_t args[1] = { key_arg };
  
  ant_value_t transformed = sv_vm_call(
    js->vm, js,
    toJSON, val,
    args, 1, NULL, false
  );
  
  if (is_err(transformed)) {
    json_capture_error(ctx, transformed);
    return js_mkundef();
  }
  if (!json_ctx_pin_value(ctx, transformed)) return js_mkundef();

  return transformed;
}

static ant_value_t json_apply_replacer(
  ant_t *js,
  const char *key,
  ant_value_t val,
  json_cycle_ctx *ctx
) {
  if (!is_callable(ctx->replacer_func)) return val;
  ant_value_t key_arg = js_mkstr(js, key, strlen(key));
  if (is_err(key_arg)) {
    json_capture_error(ctx, key_arg);
    return js_mkundef();
  }
  if (!json_ctx_pin_value(ctx, key_arg)) return js_mkundef();
  ant_value_t args[2] = { key_arg, val };
  
  ant_value_t transformed = sv_vm_call(
    js->vm, js, 
    ctx->replacer_func, ctx->holder, 
    args, 2, NULL, false
  );
  
  if (is_err(transformed)) {
    json_capture_error(ctx, transformed);
    return js_mkundef();
  }
  if (!json_ctx_pin_value(ctx, transformed)) return js_mkundef();

  return transformed;
}

static inline ant_value_t json_create_root_holder(ant_t *js, ant_value_t value, json_cycle_ctx *ctx) {
  ant_value_t holder = js_mkobj(js);
  if (is_err(holder)) return holder;
  if (!json_ctx_pin_value(ctx, holder)) return js_mkundef();
  js_set(js, holder, "", value);
  return holder;
}

static json_write_res json_write_array(ant_t *js, ant_value_t val, json_cycle_ctx *ctx) {
  ant_offset_t length = js_arr_len(js, val);
  ant_value_t saved_holder = ctx->holder;

  json_set_holder(ctx, val);
  json_out_char(&ctx->out, '[');
  ctx->depth++;

  for (ant_offset_t i = 0; i < length; i++) {
    char idxstr[32];
    uint_to_str(idxstr, sizeof(idxstr), (uint64_t)i);

    if (i) json_out_char(&ctx->out, ',');
    json_write_indent(ctx, ctx->depth);

    ant_value_t elem = js_arr_get(js, val, i);
    json_write_res res = json_write_with_key(js, idxstr, elem, ctx, 1);

    if (res == JSON_WRITE_ABORT) {
      json_set_holder(ctx, saved_holder);
      return JSON_WRITE_ABORT;
    }
  }

  ctx->depth--;
  if (length) json_write_indent(ctx, ctx->depth);
  json_out_char(&ctx->out, ']');

  json_set_holder(ctx, saved_holder);
  return json_has_abort(ctx) ? JSON_WRITE_ABORT : JSON_WRITE_OK;
}

/* Most objects reach stringify as plain data, where their own enumerable keys
   can be snapshotted as interned pointers instead of a GC array of strings. */
#define JSON_INLINE_KEYS 32

static json_write_res json_write_object(ant_t *js, ant_value_t val, json_cycle_ctx *ctx) {
  const char *inline_keys[JSON_INLINE_KEYS];
  const char **plain_keys = inline_keys;
  const char **heap_keys = NULL;

  ant_value_t keys = js_mkundef();
  ant_value_t saved_holder = ctx->holder;
  json_write_res result = JSON_WRITE_ABORT;

  int32_t plain_count = js_own_plain_keys(js, val, inline_keys, JSON_INLINE_KEYS);

  if (plain_count > JSON_INLINE_KEYS) {
    heap_keys = malloc((size_t)plain_count * sizeof(*heap_keys));
    if (!heap_keys) {
      ctx->out.oom = true;
      return JSON_WRITE_ABORT;
    }
    plain_keys = heap_keys;
    plain_count = js_own_plain_keys(js, val, heap_keys, (uint32_t)plain_count);
  }

  if (plain_count < 0) {
    plain_keys = NULL;
    keys = json_snapshot_keys(js, val);

    if (is_err(keys)) {
      json_capture_error(ctx, keys);
      return JSON_WRITE_ABORT;
    }
    if (!json_ctx_pin_value(ctx, keys)) return JSON_WRITE_ABORT;
  }

  json_set_holder(ctx, val);
  json_out_char(&ctx->out, '{');
  ctx->depth++;

  ant_offset_t key_count = plain_keys ? (ant_offset_t)plain_count : js_arr_len(js, keys);
  bool wrote_any = false;

  for (ant_offset_t i = 0; i < key_count; i++) {
    size_t key_len = 0;
    const char *key;

    if (plain_keys) {
      key = plain_keys[i];
      key_len = strlen(key);
    } else {
      key = js_getstr(js, js_arr_get(js, keys, i), &key_len);
    }

    if (!key) continue;
    if (!is_key_in_replacer_arr(js, ctx, key, key_len)) continue;

    ant_value_t prop = js_get(js, val, key);
    if (is_err(prop)) {
      json_capture_error(ctx, prop);
      goto done;
    }

    /* Emit the key optimistically; a skipped value rewinds the buffer. */
    size_t rewind = ctx->out.len;

    if (wrote_any) json_out_char(&ctx->out, ',');
    json_write_indent(ctx, ctx->depth);

    json_out_t *out = &ctx->out;
    if (!utf8_json_quote_into(&out->buf, &out->len, &out->cap, key, key_len)) out->oom = true;

    json_out_char(&ctx->out, ':');
    if (ctx->gap_len) json_out_char(&ctx->out, ' ');

    json_write_res res = json_write_with_key(js, key, prop, ctx, 0);

    if (res == JSON_WRITE_ABORT) goto done;
    if (res == JSON_WRITE_SKIP) {
      ctx->out.len = rewind;
      continue;
    }

    wrote_any = true;
  }

  ctx->depth--;
  if (wrote_any) json_write_indent(ctx, ctx->depth);
  json_out_char(&ctx->out, '}');
  result = json_has_abort(ctx) ? JSON_WRITE_ABORT : JSON_WRITE_OK;

done:
  free(heap_keys);
  json_set_holder(ctx, saved_holder);
  return result;
}

static json_write_res json_write_value(
  ant_t *js, const char *key, ant_value_t val, json_cycle_ctx *ctx, int in_array
) {
  int type = vtype(val);

  switch (type) {
    case T_NULL: json_out_write(&ctx->out, "null", 4); return JSON_WRITE_OK;
    case T_BOOL:
      if (val == js_true) json_out_write(&ctx->out, "true", 4);
      else json_out_write(&ctx->out, "false", 5);
      return JSON_WRITE_OK;

    case T_UNDEF:
    case T_FUNC:
    case T_SYMBOL:
      if (!in_array) return JSON_WRITE_SKIP;
      json_out_write(&ctx->out, "null", 4);
      return JSON_WRITE_OK;

    case T_NUM:
      json_write_number(ctx, js_getnum(val));
      return JSON_WRITE_OK;

    case T_STR:
      json_write_string(js, ctx, val);
      return JSON_WRITE_OK;

    case T_BIGINT:
      json_set_error(ctx, js_mkerr_typed(js, JS_ERR_TYPE, "Do not know how to serialize a BigInt"));
      return JSON_WRITE_ABORT;

    case T_OBJ: {
      /* SerializeJSONProperty step 4: wrappers serialize as their primitive. */
      ant_value_t prim = js_get_slot(js_as_obj(val), SLOT_PRIMITIVE);

      switch (vtype(prim)) {
        case T_NUM: json_write_number(ctx, js_to_number(js, val)); return JSON_WRITE_OK;
        case T_BOOL:
          if (prim == js_true) json_out_write(&ctx->out, "true", 4);
          else json_out_write(&ctx->out, "false", 5);
          return JSON_WRITE_OK;

        case T_STR: {
          ant_value_t str = coerce_to_str(js, val);
          if (is_err(str)) {
            json_capture_error(ctx, str);
            return JSON_WRITE_ABORT;
          }
          if (!json_ctx_pin_value(ctx, str)) return JSON_WRITE_ABORT;
          json_write_string(js, ctx, str);
          return JSON_WRITE_OK;
        }

        case T_BIGINT:
          json_set_error(ctx, js_mkerr_typed(js, JS_ERR_TYPE, "Do not know how to serialize a BigInt"));
          return JSON_WRITE_ABORT;

        default: break;
      }
      break;
    }

    case T_ARR: break;
    default: json_out_write(&ctx->out, "null", 4); return JSON_WRITE_OK;
  }

  if (json_cycle_check(ctx, val, key)) return JSON_WRITE_ABORT;
  json_cycle_push(ctx, val);

  json_write_res res = is_array_value(val)
    ? json_write_array(js, val, ctx)
    : json_write_object(js, val, ctx);

  json_cycle_pop(ctx);
  return res;
}

static json_write_res json_write_with_key(
  ant_t *js, const char *key, ant_value_t val, json_cycle_ctx *ctx, int in_array
) {
  val = json_apply_tojson(js, key, val, ctx);
  if (json_has_abort(ctx)) return JSON_WRITE_ABORT;

  val = json_apply_replacer(js, key, val, ctx);
  if (json_has_abort(ctx)) return JSON_WRITE_ABORT;

  return json_write_value(js, key, val, ctx, in_array);
}

static ant_value_t apply_reviver_call(
  ant_t *js,
  ant_value_t holder,
  const char *key,
  ant_value_t reviver,
  gc_temp_root_scope_t *roots
) {
  ant_value_t key_str = js_mkstr(js, key, strlen(key));
  if (is_err(key_str)) return key_str;
  if (!json_temp_pin(roots, key_str)) return json_parse_oom(js);
  ant_value_t current_value = js_get(js, holder, key);
  ant_value_t call_args[2] = { key_str, current_value };
  
  ant_value_t result = sv_vm_call(
    js->vm, js, reviver, holder,
    call_args, 2, NULL, false
  );
  if (!is_err(result) && !json_temp_pin(roots, result)) return json_parse_oom(js);
  
  return result;
}

static void apply_reviver_to_array(
  ant_t *js,
  ant_value_t value,
  ant_value_t reviver,
  gc_temp_root_scope_t *roots
) {
  ant_offset_t length = js_arr_len(js, value);

  for (ant_offset_t i = 0; i < length; i++) {
  char idxstr[32];
  size_t idx_len = uint_to_str(idxstr, sizeof(idxstr), (uint64_t)i);
  ant_value_t new_elem = apply_reviver(js, value, idxstr, reviver, roots);
  if (vtype(new_elem) == T_UNDEF) js_delete_prop(js, value, idxstr, idx_len);
  else {
    ant_value_t key_val = js_mkstr(js, idxstr, idx_len);
    if (is_err(key_val)) return;
    if (!json_temp_pin(roots, key_val)) return;
    js_setprop(js, value, key_val, new_elem);
  }}
}

static void apply_reviver_to_object(
  ant_t *js,
  ant_value_t value,
  ant_value_t reviver,
  gc_temp_root_scope_t *roots
) {
  ant_value_t keys = json_snapshot_keys(js, value);
  if (is_err(keys) || vtype(keys) != T_ARR) return;
  if (!json_temp_pin(roots, keys)) return;

  ant_offset_t key_count = js_arr_len(js, keys);
  for (ant_offset_t i = 0; i < key_count; i++) {
    ant_value_t key_val = js_arr_get(js, keys, i);
    size_t key_len = 0;
    char *key = js_getstr(js, key_val, &key_len);
    if (!key) continue;
    ant_value_t new_val = apply_reviver(js, value, key, reviver, roots);
    if (vtype(new_val) == T_UNDEF) js_delete_prop(js, value, key, key_len);
    else js_set(js, value, key, new_val);
  }
}

static ant_value_t apply_reviver(
  ant_t *js,
  ant_value_t holder,
  const char *key,
  ant_value_t reviver,
  gc_temp_root_scope_t *roots
) {
  ant_value_t val = js_get(js, holder, key);
  
  if (is_array_value(val)) apply_reviver_to_array(js, val, reviver, roots);
  else if (vtype(val) == T_OBJ) apply_reviver_to_object(js, val, reviver, roots);

  return apply_reviver_call(js, holder, key, reviver, roots);
}

ant_value_t js_json_parse(ant_t *js, ant_value_t *args, int nargs) {
  if (nargs < 1) return js_mkerr(js, "JSON.parse() requires at least 1 argument");
  if (vtype(args[0]) != T_STR) return js_mkerr(js, "JSON.parse() argument must be a string");
  gc_temp_root_scope_t temp_roots;
  gc_temp_root_scope_begin(js, &temp_roots);
  
  size_t len;
  char *json_str = js_getstr(js, args[0], &len);
  
  yyjson_doc *doc = yyjson_read(json_str, len, 0);
  
  if (!doc) {
    gc_temp_root_scope_end(&temp_roots);
    return js_mkerr_typed(js, JS_ERR_SYNTAX, "JSON.parse: unexpected character");
  }
  
  ant_value_t result = yyjson_to_jsval(js, yyjson_doc_get_root(doc));
  yyjson_doc_free(doc);

  if (is_err(result)) {
    gc_temp_root_scope_end(&temp_roots);
    return result;
  }

  if (!json_temp_pin(&temp_roots, result)) {
    gc_temp_root_scope_end(&temp_roots);
    return json_parse_oom(js);
  }

  if (nargs >= 2 && is_callable(args[1])) {
    ant_value_t reviver = args[1];
    if (!json_temp_pin(&temp_roots, reviver)) {
      gc_temp_root_scope_end(&temp_roots);
      return json_parse_oom(js);
    }
    ant_value_t root = js_mkobj(js);
    if (is_err(root)) {
      gc_temp_root_scope_end(&temp_roots);
      return root;
    }
    if (!json_temp_pin(&temp_roots, root)) {
      gc_temp_root_scope_end(&temp_roots);
      return json_parse_oom(js);
    }
    js_set(js, root, "", result);
    result = apply_reviver(js, root, "", reviver, &temp_roots);
  }
  
  gc_temp_root_scope_end(&temp_roots);
  return result;
}

ant_value_t json_parse_value(ant_t *js, ant_value_t value) {
  ant_value_t args[1] = { value };
  return js_json_parse(js, args, 1);
}

/* SerializeJSONProperty step 6: the gap is at most 10 spaces, or the first 10
   UTF-16 units of a string `space`. */
static void json_setup_gap(ant_t *js, json_cycle_ctx *ctx, ant_value_t *args, int nargs) {
  if (nargs < 3) return;

  ant_value_t space = args[2];

  /* Step 5: a Number or String wrapper contributes its primitive. */
  if (vtype(space) == T_OBJ) {
    ant_value_t prim = js_get_slot(js_as_obj(space), SLOT_PRIMITIVE);
    if (vtype(prim) == T_NUM) space = js_mknum(js_to_number(js, space));
    else if (vtype(prim) == T_STR) space = coerce_to_str(js, space);
    if (is_err(space)) return;
  }

  int type = vtype(space);

  if (type == T_NUM) {
    double n = js_getnum(space);
    if (!(n >= 1)) return;
    size_t count = n > 10 ? 10 : (size_t)n;
    memset(ctx->gap, ' ', count);
    ctx->gap_len = count;
    return;
  }

  if (type != T_STR) return;

  size_t byte_len = 0;
  char *str = js_getstr(js, space, &byte_len);
  if (!str || !byte_len) return;

  size_t take = byte_len;
  if (utf16_strlen(str, byte_len) > 10) {
    int off = utf16_index_to_byte_offset(str, byte_len, 10, NULL);
    if (off >= 0) take = (size_t)off;
  }
  if (take > sizeof(ctx->gap)) take = sizeof(ctx->gap);

  memcpy(ctx->gap, str, take);
  ctx->gap_len = take;
}

ant_value_t js_json_stringify(ant_t *js, ant_value_t *args, int nargs) {
  ant_value_t result;

  json_cycle_ctx ctx = {
    .js = js,
    .replacer_func = js_mkundef(),
    .replacer_arr = js_mkundef(),
    .error = js_mkundef(),
    .holder = js_mkundef(),
  };
  
  ant_value_t root_holder = js_mkundef();

  if (nargs < 1) return js_mkerr(js, "JSON.stringify() requires at least 1 argument");
  gc_temp_root_scope_begin(js, &ctx.temp_roots);
  ctx.error_handle = gc_temp_root_add(&ctx.temp_roots, ctx.error);
  ctx.holder_handle = gc_temp_root_add(&ctx.temp_roots, ctx.holder);
  
  if (!gc_temp_root_handle_valid(ctx.error_handle) || !gc_temp_root_handle_valid(ctx.holder_handle)) {
    gc_temp_root_scope_end(&ctx.temp_roots);
    return json_stringify_oom(js);
  }
  
  if (!json_ctx_pin_value(&ctx, args[0])) {
    result = ctx.error;
    goto cleanup;
  }
  
  int top_type = vtype(args[0]);
  
  if (nargs < 2 && top_type == T_STR) {
    json_write_string(js, &ctx, args[0]);
    if (ctx.out.oom) {
      result = json_stringify_oom(js);
      goto cleanup;
    }
    result = js_mkstr(js, ctx.out.buf, ctx.out.len);
    goto cleanup;
  }

  if (nargs >= 2) {
  ant_value_t replacer = args[1];
  if (is_callable(replacer)) {
  ctx.replacer_func = replacer;
  if (!json_ctx_pin_value(&ctx, replacer)) {
    result = ctx.error;
    goto cleanup;
  }}
  
  else if (is_special_object(replacer)) {
  ant_value_t len_val = js_get(js, replacer, "length");
  
  if (vtype(len_val) == T_NUM) {
    ctx.replacer_arr = replacer;
    ctx.replacer_arr_len = (int)js_getnum(len_val);
    if (!json_ctx_pin_value(&ctx, replacer)) {
      result = ctx.error;
      goto cleanup;
    }
  }}} 
  
  json_setup_gap(js, &ctx, args, nargs);

  root_holder = json_create_root_holder(js, args[0], &ctx);
  if (is_err(root_holder)) {
    result = root_holder;
    goto cleanup;
  }
  
  if (vtype(root_holder) == T_UNDEF && vtype(ctx.error) != T_UNDEF) {
    result = ctx.error;
    goto cleanup;
  }
  
  json_set_holder(&ctx, root_holder);
  json_write_res root = json_write_with_key(js, "", args[0], &ctx, 0);

  if (vtype(ctx.error) != T_UNDEF) {
    ant_value_t error = json_normalize_error(ctx.error);
    result = is_err(error) ? error : js_throw(js, error);
    goto cleanup;
  }

  if (ctx.has_cycle) {
    result = json_cycle_error(js, &ctx);
    goto cleanup;
  }

  if (ctx.out.oom) {
    result = json_stringify_oom(js);
    goto cleanup;
  }

  if (root == JSON_WRITE_SKIP) {
    result = js_mkundef();
    goto cleanup;
  }

  result = js_mkstr(js, ctx.out.buf, ctx.out.len);

cleanup:
  free(ctx.out.buf);
  free(ctx.stack);
  gc_temp_root_scope_end(&ctx.temp_roots);
  return result;
}

ant_value_t json_stringify_value(ant_t *js, ant_value_t value) {
  ant_value_t args[1] = { value };
  return js_json_stringify(js, args, 1);
}

void init_json_module(ant_t *js) {
  ant_value_t json_obj = js_mkobj(js);
  
  js_set(js, json_obj, "parse", js_mkfun(js_json_parse));
  js_set(js, json_obj, "stringify", js_mkfun(js_json_stringify));
  
  js_set_sym(js, json_obj, get_toStringTag_sym(), js_mkstr(js, "JSON", 4));
  js_set(js, js_glob(js), "JSON", json_obj);
}
