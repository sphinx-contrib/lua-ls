Refs
====

.. container:: regression

   .. lua:data:: ref_target

      Ref from inside: :lua:obj:`ref_target`.

   Ref from outside: :lua:obj:`ref_target`.

   .. lua:data:: mod.ref_target

      Ref from inside: :lua:obj:`ref_target`.

      Absolute ref from inside: :lua:obj:`mod.ref_target`.

   Ref from outside: :lua:obj:`mod.ref_target`.

   Ref from outside short: :lua:obj:`~mod.ref_target`.

   .. lua:module:: ref_module

   .. lua:data:: ref_target

      Ref from inside: :lua:obj:`ref_target`.

      Absolute ref from inside: :lua:obj:`ref_module.ref_target`.

   Ref from outside: :lua:obj:`ref_target`.

   Absolute ref from outside: :lua:obj:`ref_module.ref_target`.

   .. lua:class:: refClass

      .. lua:data:: ref_target

         Ref from inside: :lua:obj:`ref_target`.

      Ref from a class: :lua:obj:`ref_target`.

      Semi-absolute from a class: :lua:obj:`refClass.ref_target`.

      Absolute from a class: :lua:obj:`ref_module.refClass.ref_target`.

      .. lua:class:: refSubClass

         .. lua:data:: ref_target

         Ref from a class: :lua:obj:`ref_target`.

         Ref from a class to containing class: :lua:obj:`refSubClass` (should not work).

         Semi-absolute ref from a class to containing class: :lua:obj:`refClass.refSubClass`.

   Ref: :lua:obj:`ref_processing.data`, :lua:obj:`ref_processing.function`,
   :lua:obj:`ref_processing.method`, :lua:obj:`ref_processing.classmethod`,
   :lua:obj:`ref_processing.staticmethod`, :lua:obj:`ref_processing.deprecated`.

   Ref with explicit title: :lua:obj:`explicit.title <ref_processing.classmethod>`.

Targets
-------

.. lua:module:: ref_processing

.. lua:data:: data

.. lua:function:: function

.. lua:method:: method

.. lua:classmethod:: classmethod

.. lua:staticmethod:: staticmethod

.. lua:data:: deprecated
   :deprecated:
