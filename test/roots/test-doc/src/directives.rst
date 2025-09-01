Directives
==========

.. container:: regression

   .. lua:function:: function_simple

      Description

   .. lua:function:: function_no_args_parens()

      Description

   .. lua:function:: function_untyped_args(a, b, c)

      Description

   .. lua:function:: function_typed_args(a: integer, b: string)

      Description

   .. lua:function:: function_typed_optional_args(a: integer?)

      Description

   .. lua:function:: function_typed_args_crossrefs(T: integer, b: T)

      Description

   .. lua:function:: function_return_type() -> integer

      Description

   .. lua:function:: function_return_types() -> integer, boolean

      Description

   .. lua:function:: function_optional_return_types() -> integer?

      Description

   .. lua:function:: function_named_return_types() -> a: integer, b: boolean

      Description

   .. lua:function:: function_named_optional_return_types() -> a: integer?

      Description

   .. lua:function:: function_return_types_crossrefs() -> T: string, a: T

      Description

   .. lua:function:: function_generics<T>

      Description

   .. lua:function:: function_generics_return<T> -> T[]

      Description

   .. lua:function:: function_generics_args_and_return<T>(...: T) -> T[]

      Description

   .. lua:function:: function_complex_types(T: integer, b: table<T, target_module.T>, c: fun(T: T, ...) -> (T: T, ...)) -> a: table<string, string>, ...: fun(a: integer, ...) -> (a: integer, ...)

      Description

   .. lua:function:: function_complex_types(T: integer, b: table<T, target_module.T>, c: fun(T: T, ...): (T: T, ...)): a: table<string, string>, ...: fun(a: integer, ...): (a: integer, ...)

      Description

   .. lua:function:: function_param_return_doc(x: integer, y: T?) -> a: integer, b: T?

      :param x: Description x
      :type x: integer
      :param y: Description y
      :type y: T?
      :return a: Description b
      :rtype a: integer
      :return b: Description b
      :rtype b: T?

   .. lua:method:: method

      Description

   .. lua:method:: cls.method_outside_of_class

      Description

   .. lua:classmethod:: classmethod

      Description

   .. lua:classmethod:: cls.classmethod_outside_of_class

      Description

   .. lua:staticmethod:: staticmethod

      Description

   .. lua:staticmethod:: cls.staticmethod_outside_of_class

      Description

   .. lua:data:: data_simple

      Description

   .. lua:data:: data_type_colon: T

      Description

   .. lua:data:: data_type_eq = T

      Description

   .. lua:data:: data_type T

      Description

   .. lua:data:: data_type_broken: UnknownType

      Description

   .. lua:data:: data_type_nested: target_module.T

      Description

   .. lua:attribute:: attribute

      Description

   .. lua:attribute:: cls.attribute_outside_of_class

      Description

   .. lua:class:: class_simple

      Description

   .. lua:class:: class_one_base: T

      Description

   .. lua:class:: class_multiple_bases: T, target_module.T, { [string]: UnknownType }

      Description

   .. lua:class:: class_generic<T>

      Description

   .. lua:class:: class_generic_multiple_types<U, V>

      Description

   .. lua:class:: class_generic_with_base<T>: T[]

      Description

   .. lua:class:: class_members

      .. lua:data:: class_data

      .. lua:function:: class_function

      .. lua:method:: class_method

   .. lua:class:: class_ctor(a: T)

   .. lua:class:: class_bases_and_ctor: T
                  class_bases_and_ctor(a: T)

   .. lua:alias:: alias_simple

   .. lua:alias:: alias_type_colon: T

   .. lua:alias:: alias_type_eq = T

   .. lua:alias:: alias_type T

   .. lua:alias:: alias_generic<T> T[]

   .. lua:alias:: alias_strings = "a|b" | "c" | "d"

   .. lua:alias:: alias_members

      .. lua:data:: alias_data

      .. lua:function:: alias_function

      .. lua:method:: alias_method

   .. lua:enum:: enum_simple

   .. lua:enum:: enum_generic<T>

   .. lua:enum:: enum_members

      .. lua:data:: enum_data

      .. lua:function:: enum_function

      .. lua:method:: enum_method

   .. lua:table:: table_simple

   .. lua:table:: table_members

      .. lua:data:: table_data

      .. lua:function:: table_function

      .. lua:method:: table_method

Targets
-------

.. lua:alias:: T = integer

.. lua:alias:: target_module.T = integer
