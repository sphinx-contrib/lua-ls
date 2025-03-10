Refs
====

.. lua:data:: refTarget

   Ref from inside: :lua:obj:`refTarget`.

Ref from outside: :lua:obj:`refTarget`.

.. lua:data:: mod.refTarget

   Ref from inside: :lua:obj:`refTarget`.

   Absolute ref from inside: :lua:obj:`mod.refTarget`.

Ref from outside: :lua:obj:`mod.refTarget`.

Ref from outside short: :lua:obj:`~mod.refTarget`.

.. lua:module:: refModule

.. lua:data:: refTarget

   Ref from inside: :lua:obj:`refTarget`.

   Absolute ref from inside: :lua:obj:`refModule.refTarget`.

Ref from outside: :lua:obj:`refTarget`.

Absolute ref from outside: :lua:obj:`refModule.refTarget`.

.. lua:class:: refClass

   .. lua:data:: refTarget

      Ref from inside: :lua:obj:`refTarget`.

   Ref from a class: :lua:obj:`refTarget`.

   Semi-absolute from a class: :lua:obj:`refClass.refTarget`.

   Absolute from a class: :lua:obj:`refModule.refClass.refTarget`.

   .. lua:class:: refSubClass

      .. lua:data:: refTarget

      Ref from a class: :lua:obj:`refTarget`.

      Ref from a class to containing class: :lua:obj:`refSubClass` (should not work).

      Semi-absolute ref from a class to containing class: :lua:obj:`refClass.refSubClass`.

.. lua:module:: refProcessing

.. lua:data:: data

.. lua:function:: function

.. lua:method:: method

.. lua:classmethod:: classmethod

.. lua:staticmethod:: staticmethod

Ref: :lua:obj:`refProcessing.data`, :lua:obj:`refProcessing.function`,
:lua:obj:`refProcessing.method`, :lua:obj:`refProcessing.classmethod`,
:lua:obj:`refProcessing.staticmethod`.

Ref with explicit title: :lua:obj:`title <refProcessing.classmethod>`.
