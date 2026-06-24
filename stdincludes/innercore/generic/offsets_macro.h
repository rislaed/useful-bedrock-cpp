#pragma once

#include "common_macro.h"


namespace internal {
	constexpr int calc_pad_aligned(int this_ofs, int this_align, int last_ofs) {
		return this_ofs - ((last_ofs + this_align - 1) / this_align) * this_align;
	}

	template<int Pad>
	struct PaddedFieldPad { char __pad[Pad]; };
	template<>
	struct PaddedFieldPad<0>{};

	template<typename T, int Idx>
	struct VerifyOffsets {
		static constexpr int offset = T::template __OffsetOf<Idx>::offset;
	};

	template<typename... Ps>
	struct ParentsOffset : Ps... { char base; };
}

#define __TEST__DBG_OFFSETS_REF_STRUCT
#define __IF_DEFINED_DBG_OFFSETS_REF_STRUCT IFN(MACRO_UTIL_CONCAT(__TEST__, DBG_OFFSETS_REF_STRUCT))


#ifdef __INTELLISENSE__
    #define __INTELLISENSE_OFFSET_FALLBACK { static constexpr int offset = 0; }
#else
    #define __INTELLISENSE_OFFSET_FALLBACK
#endif

#define HZ_DECL_STRUCT_EX(TYPE, BASE_OFFSET) \
	using __ThisType = TYPE; \
	using __ThisTypeOffsets = __offsets::TYPE; \
	enum { __CounterBase = __COUNTER__ }; \
	template<int I, typename VoidT> struct __OffsetOf __INTELLISENSE_OFFSET_FALLBACK ; \
	template<typename VoidT> struct __OffsetOf<-1, VoidT> { static constexpr int offset = BASE_OFFSET; };

#define HZ_DECL_PLAIN_STRUCT(TYPE) HZ_DECL_STRUCT_EX(TYPE, 0)
#define HZ_DECL_VTABLE_STRUCT(TYPE) HZ_DECL_STRUCT_EX(TYPE, sizeof(void*))
#define HZ_DECL_INHERITED_STRUCT(TYPE, PARENT) HZ_DECL_STRUCT_EX(TYPE, __builtin_offsetof(internal::ParentsOffset<PARENT>, base))


#define HZ_DECL_FIELD_AND_PAD_IMPL(LAST_IDX, OFFSET, NAME, ...) \
	char __pad##NAME[OFFSET - __OffsetOf<LAST_IDX, void>::offset]; \
	__VA_ARGS__ NAME

#define HZ_DECL_FIELD_IMPL(LAST_IDX, IDX, OFFSET, NAME, ...) \
	template<typename VoidT> struct __OffsetOf<IDX, VoidT> { \
		__IF_DEFINED_DBG_OFFSETS_REF_STRUCT(static_assert(__builtin_offsetof(DBG_OFFSETS_REF_STRUCT, NAME) == OFFSET, "reference offset mismatch " #NAME);) \
		static_assert(OFFSET % alignof(__VA_ARGS__) == 0, "alignment is incorrect " #NAME); \
		static constexpr int offset = OFFSET + sizeof(__VA_ARGS__); \
	}; \
	HZ_DECL_FIELD_AND_PAD_IMPL(LAST_IDX, OFFSET, NAME, __VA_ARGS__)


#define HZ_DECL_STRUCT_SIZE_PAD_EX(FIELD_CNT, SIZE) \
	template<typename VoidT> struct __OffsetOf<FIELD_CNT, VoidT> { static constexpr int offset = 0x7fffffff; }; \
	static_assert(SIZE - __OffsetOf<FIELD_CNT - 1, void>::offset >= 0, "size pad verify failed " #SIZE); \
	struct : internal::PaddedFieldPad<SIZE - __OffsetOf<FIELD_CNT - 1, void>::offset> {} __struct_size;

#define HZ_FIELD_IMPL2(IDX, TYPE, NAME) HZ_DECL_FIELD_IMPL((IDX) - 1, IDX, __ThisTypeOffsets::NAME, NAME, TYPE)
#define HZ_FIELD_IMPL(CTR, BASE, TYPE, NAME) HZ_FIELD_IMPL2((CTR) - (BASE) - 1, TYPE, NAME)
#define HZ_DECL_FIELD(TYPE, NAME) HZ_FIELD_IMPL(__COUNTER__, __ThisType::__CounterBase, TYPE, NAME)

#define HZ_FIELD_T_IMPL2(IDX, TYPE, NAME) HZ_DECL_FIELD_IMPL((IDX) - 1, IDX, __ThisTypeOffsets::NAME, NAME, MACRO_UTIL_EXPAND TYPE)
#define HZ_FIELD_T_IMPL(CTR, BASE, TYPE, NAME) HZ_FIELD_T_IMPL2((CTR) - (BASE) - 1, TYPE, NAME)
#define HZ_DECL_FIELD_T(TYPE, NAME) HZ_FIELD_T_IMPL(__COUNTER__, __ThisType::__CounterBase, TYPE, NAME)

#define HZ_STRUCT_PAD_IMPL2(IDX) HZ_DECL_STRUCT_SIZE_PAD_EX(IDX, __ThisTypeOffsets::__struct_size)
#define HZ_STRUCT_PAD_IMPL(CTR, BASE) HZ_STRUCT_PAD_IMPL2((CTR) - (BASE) - 1)
#define HZ_DECL_STRUCT_SIZE_PAD() HZ_STRUCT_PAD_IMPL(__COUNTER__, __ThisType::__CounterBase)

#define HZ_DECL_FIELD_IDX(IDX, TYPE, NAME) HZ_DECL_FIELD_IMPL(IDX - 1, IDX, __ThisTypeOffsets::NAME, NAME, TYPE)
#define HZ_DECL_FIELD_T_IDX(IDX, TYPE, NAME) HZ_DECL_FIELD_IMPL(IDX - 1, IDX, __ThisTypeOffsets::NAME, NAME, MACRO_UTIL_EXPAND TYPE)
#define HZ_DECL_STRUCT_SIZE_PAD_IDX(FIELD_CNT) HZ_DECL_STRUCT_SIZE_PAD_EX(FIELD_CNT, __ThisTypeOffsets::__struct_size)


#define HZ_DECL_STRUCT_SIZE_VER_EX(FIELD_CNT, SIZE) \
	static_assert(SIZE - __OffsetOf<FIELD_CNT - 1, void>::offset == 0, "size verify failed " #SIZE); 
#define HZ_DECL_STRUCT_SIZE_VER(FIELD_CNT) HZ_DECL_STRUCT_SIZE_VER_EX(FIELD_CNT, __ThisTypeOffsets::__struct_size)

#define HZ_DECL_STRUCT_VERIFY(TYPE) namespace internal { inline static VerifyOffsets<TYPE, 0> __verify##TYPE; }
#define HZ_VERIFY_FIELD_OFFSET(STRUCT, FIELD) static_assert(__builtin_offsetof(STRUCT, FIELD) == STRUCT::__ThisTypeOffsets::FIELD, #STRUCT "::" #FIELD " offset validation failed");
#define HZ_VERIFY_STRUCT_SIZE(STRUCT) static_assert(sizeof(STRUCT) == STRUCT::__ThisTypeOffsets::__struct_size, #STRUCT " size validation failed");

#define HZ_DECL_OFFSETS_FOR(STRUCT) struct STRUCT
#define HZ_DECL_OFFSETS_FOR_ANON HZ_DECL_OFFSETS_FOR
#define HZ_DECL_OFFSETS_FOR_NS(NAME) HZ_DECL_OFFSETS_FOR(NAME)
#define HZ_DECL_OFFSET(OFFSET, NAME) static constexpr int NAME = OFFSET;
#define HZ_DECL_OFFSET_PTR HZ_DECL_OFFSET
#define HZ_DECL_SIZE(SIZE) static constexpr int __struct_size = SIZE;
#define HZ_DECL_OFFSETS_FOR_CHILD(NAME) struct NAME

#define HZ_OFS_PTR(PTR, OFFSET, ...) (*(__VA_ARGS__ *)((unsigned char *)(PTR) + (__offsets::OFFSET)))
#define HZ_NOT_OFS_PTR(PTR, OFFSET, ...) ((__VA_ARGS__ *)((unsigned char *)(PTR) + (__offsets::OFFSET)))
