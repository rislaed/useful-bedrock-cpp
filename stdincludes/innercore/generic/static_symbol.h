#pragma once

#include "common_macro.h"


struct InitOnDemandSymbolTypeless {
	InitOnDemandSymbolTypeless(const char* name) : name(name) {}
	void* get() const {
		// we dont care, if it is accessed from multiple threads,
		// in worst case it will be initialized twice
		if (IC_UNLIKELY(value == (void*) 1)) {
			value = (void*) SYMBOL("mcpe", name);
			Logger::debug("InnerCore-StaticSymbols", "initialized static symbol %s with pointer %p", name, value);
		}
		return value;
	}
private:
	mutable void* value = (void*) 1;
	const char* name;
};

template<typename T>
struct InitOnDemandSymbol;

template<typename R, typename... Args>
struct InitOnDemandSymbol<R (Args...)> : InitOnDemandSymbolTypeless {
	using InitOnDemandSymbolTypeless::InitOnDemandSymbolTypeless;
	using FnT = R(*)(Args...);
	operator FnT() const { return get(); }
	FnT get() const { return (FnT) InitOnDemandSymbolTypeless::get(); }
};

template<typename PtrT>
struct InitOnDemandSymbol<PtrT*> : InitOnDemandSymbolTypeless {
	using InitOnDemandSymbolTypeless::InitOnDemandSymbolTypeless;
	operator PtrT*() const { return get(); }
	PtrT* get() const { return (PtrT*) InitOnDemandSymbolTypeless::get(); }
};


#define STATIC_SYMBOL_WITH_RESULT(VAR_NAME, SYMBOL_NAME, RESULT_TYPE, PARAM_TYPES) static InitOnDemandSymbol<RESULT_TYPE PARAM_TYPES> VAR_NAME(SYMBOL_NAME);
#define STATIC_SYMBOL_VOID_PTR(VAR_NAME, SYMBOL_NAME) static InitOnDemandSymbol<void*> VAR_NAME(SYMBOL_NAME);

#define LINK_VOID_METHOD(SIGNATURE, PARAMS, SYMBOL_NAME, PARAMS_CALL) inline SIGNATURE PARAMS { STATIC_SYMBOL_WITH_RESULT(func, SYMBOL_NAME, void, MACRO_UTIL_ADD_FIRST(void*, PARAMS)); func MACRO_UTIL_ADD_FIRST(this, PARAMS_CALL); }
#define LINK_RESULT_METHOD(RESULT, SIGNATURE, PARAMS, SYMBOL_NAME, PARAMS_CALL) inline RESULT SIGNATURE PARAMS { STATIC_SYMBOL_WITH_RESULT(func, SYMBOL_NAME, RESULT, MACRO_UTIL_ADD_FIRST(void*, PARAMS)); return func MACRO_UTIL_ADD_FIRST(this, PARAMS_CALL); }
#define LINK_DESTRUCTOR(TYPE_NAME, SYMBOL_NAME) LINK_VOID_METHOD(~TYPE_NAME, (), SYMBOL_NAME, ())
