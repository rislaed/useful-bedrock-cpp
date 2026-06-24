#ifndef INNER_CORE_VA_OPT_H
#define INNER_CORE_VA_OPT_H

#define VA_ARG1(A0,A1,...) A1
// VA_EMPTY works only if __VA_OPT__ is supported, else always -> 1
#define VA_EMPTY(...) VA_ARG1(__VA_OPT__(,)0,1,)

#define VA_OPT_SUPPORT ! VA_EMPTY

#if VA_OPT_SUPPORT(?)
	#define IS_EMPTY(...) VA_EMPTY(__VA_ARGS__)
	#define IFN(...) VA_EAT __VA_OPT__(()VA_IDENT)
	#define IFE(...) VA_IDENT __VA_OPT__(()VA_EAT)
	#define IFNE(...) VA_ARGTAIL __VA_OPT__((,)VA_ARG0)
#else
	#define IS_EMPTY(...) IFP(IBP(__VA_ARGS__))(IE_GEN_0,IE_IBP)(__VA_ARGS__)
	#define IFN(...) IFP(IBP(__VA_ARGS__))(GEN_IDENT,EAT_OR_IDENT)(__VA_ARGS__)
	#define IFE(...) IFP(IBP(__VA_ARGS__))(GEN_EAT,IDENT_OR_EAT)(__VA_ARGS__)
	#define IFNE(...) IFP(IBP(__VA_ARGS__))(GEN_ARGTAIL,ARG0_OR_TAIL)(__VA_ARGS__)
#endif

#define VA_EAT(...)
#define VA_IDENT(...) __VA_ARGS__
#define VA_ARG0_(A0,...) A0
#define VA_ARG0(...) VA_ARG0_(__VA_ARGS__)
#define VA_ARGTAIL_(A0,...) __VA_ARGS__
#define VA_ARGTAIL(...) VA_ARGTAIL_(__VA_ARGS__)

// IFP helper macros to test IBP for IFN and IS_EMPTY
#define IFP_0(T,...) __VA_ARGS__
#define IFP_1(T,...) T

#define IFP_CAT(A,...) A##__VA_ARGS__
#define IFP(BP) IFP_CAT(IFP_,BP)

// IS_BEGIN_PAREN helper macros adapted from BOOST VMD
#define IBP_CAT_(A,...) A##__VA_ARGS__
#define IBP_CAT(A,...) IBP_CAT_(A,__VA_ARGS__)

#define IBP_ARG0_(A,...) A
#define IBP_ARG0(...) IBP_ARG0_(__VA_ARGS__)

#define IBP_IS_ARGS(...) 1

#define IBP_1 1,
#define IBP_IBP_IS_ARGS 0,

// IBP IS_BEGIN_PAREN returns 1 or 0 if ... ARGS is parenthesised
#define IBP(...) IBP_ARG0(IBP_CAT(IBP_, IBP_IS_ARGS __VA_ARGS__))

// IFN, IFE, IFNE and IF_EMPTY helpers without __VA_OPT__ support
#if !VA_OPT_SUPPORT(?)
	#define IBP_(T,...) IBP_ARG0(IBP_CAT(IF##T##_, IBP_IS_ARGS __VA_ARGS__))

	// IS_EMPTY helper macros, depend on IBP
	#define IE_REDUCE_IBP(...) ()
	#define IE_GEN_0(...) 0
	#define IE_IBP(...) IBP(IE_REDUCE_IBP __VA_ARGS__ ())

	#define GEN_IDENT(...) VA_IDENT
	#define GEN_EAT(...) VA_EAT
	#define GEN_ARGTAIL(...) VA_ARGTAIL
	#define GEN_ARG0(...) VA_ARG0

	// IFN, IFE, IFNE helper macros
	#define EAT_OR_IDENT(...) IBP_(N,IE_REDUCE_IBP __VA_ARGS__ ())
	#define IFN_1 VA_EAT,
	#define IFN_IBP_IS_ARGS VA_IDENT,

	#define IDENT_OR_EAT(...) IBP_(E,IE_REDUCE_IBP __VA_ARGS__ ())
	#define IFE_1 VA_IDENT,
	#define IFE_IBP_IS_ARGS VA_EAT,

	#define ARG0_OR_TAIL(...) IBP_(NE,IE_REDUCE_IBP __VA_ARGS__ ())
	#define IFNE_1 VA_ARGTAIL,
	#define IFNE_IBP_IS_ARGS VA_ARG0,
#endif // IFN and IF_EMPTY defs

#endif // INNER_CORE_VA_OPT_H


#ifndef INNER_CORE_MACRO_H
#define INNER_CORE_MACRO_H

#include <dlfcn.h>
#include <symbol.h>
#include <logger.h>
#include <type_traits>


// attributes

#define IC_UNUSED(X) ((void) (X))
#define IC_MAYBE_UNUSED __attribute__((unused))
#define IC_NOINLINE __attribute__((noinline))
#define IC_LIKELY(X) __builtin_expect(!!(X), 1)
#define IC_UNLIKELY(X) __builtin_expect(!!(X), 0)
#define IC_PREFETCH_EX(X, T) __builtin_prefetch((X), T)
#define IC_PREFETCH(X) IC_PREFETCH_EX(X, 3)
#define IC_PREFETCH_WEAK(X) IC_PREFETCH_EX(X, 0)
#define IC_FORCEINLINE __attribute__((always_inline)) inline
#ifdef __clang__
	#define IC_EXPORT_SYMBOL __attribute__((used))
#else
	#define IC_EXPORT_SYMBOL __attribute__((externally_visible)) __attribute__((used))
#endif


// macro utils

#define MACRO_UTIL_CONCAT0(A, B) A ## B
#define MACRO_UTIL_CONCAT(A, B) MACRO_UTIL_CONCAT0(A, B) 
#define MACRO_UTIL_NOTHING(...)
#define MACRO_UTIL_EXPAND(...) __VA_ARGS__
#define MACRO_UTIL_COMMA(...) IFN(__VA_ARGS__)(,)
#define MACRO_UTIL_ADD_FIRST(X, SEQ) (MACRO_UTIL_EXPAND(X MACRO_UTIL_COMMA SEQ MACRO_UTIL_EXPAND SEQ))
#define MACRO_UTIL_ADD_LAST(X, SEQ) (MACRO_UTIL_EXPAND(MACRO_UTIL_EXPAND SEQ MACRO_UTIL_COMMA SEQ X))


// other

#define IC_CHECK_RETURN_ADDR(VAR, SYMBOL_ADDR, INDEX, SPAN_START, SPAN_END) \
	bool VAR = false; \
	{ \
		int _ret_addr_delta = int((char*) __builtin_return_address(INDEX) - (char*) SYMBOL_ADDR); \
		VAR = _ret_addr_delta >= (SPAN_START) && _ret_addr_delta < (SPAN_END); \
	}

#endif // INNER_CORE_MACRO_H
