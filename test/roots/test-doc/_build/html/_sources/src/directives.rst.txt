Directives
==========

Type Targets
------------

.. lua:alias:: T = integer

.. lua:alias:: mod.T = integer

Data
----

.. lua:data:: simpleData

   Description

.. lua:data:: dataWithTypeColon: T

   Description

.. lua:data:: dataWithTypeEq = T

   Description

.. lua:data:: dataWithType T

   Description

.. lua:data:: dataWithBrokenType: UnknownType

   Description

.. lua:data:: dataWithNestedType: mod.T

   Description

.. lua:const:: simpleConst

   Description

.. lua:attribute:: simpleAttribute

   Description

Function
--------

.. lua:function:: simpleFunction

   Description

.. lua:function:: functionWithEmptyParams()

   Description

.. lua:function:: functionWithParams(a, b, c)

   Description

.. lua:function:: functionWithTypedParams(T: integer, b: table<T, mod.T>, c: fun(T: T, ...): (T: T, ...))

   Description

.. lua:function:: functionWithReturn -> integer

   Description

.. lua:function:: functionWithReturnAndParams(a: integer) -> integer

   Description

.. lua:function:: functionWithComplexReturnType() -> a: table<string, string>, ...: fun(a: integer, ...): (a: integer, ...)

   Description

.. lua:function:: functionWithOptionalTypes(x: integer?) -> y: integer?

   :param x: Description
   :type x: integer?
   :return y: Description
   :rtype y: integer?

.. lua:method:: simpleMethod

   Description

.. lua:classmethod:: simpleClassmethod

   Description

.. lua:staticmethod:: simpleStaticmethod

   Description

Class
-----

.. lua:class:: simpleClass

   Description

.. lua:class:: classWithBase: T

   Description

.. lua:class:: classWithSeveralBases: T, mod.T, { [string]: UnknownType }

   Description

.. lua:class:: classWithMembers

   .. lua:data:: classData

   .. lua:function:: classFunction

Alias
-----

.. lua:alias:: simpleAlias

.. lua:alias:: aliasWithTypeColon: T

.. lua:alias:: aliasWithTypeEq = T

.. lua:alias:: aliasWithType T

.. lua:alias:: aliasWithMembers

   .. lua:data:: aliasData

   .. lua:function:: aliasFunction
