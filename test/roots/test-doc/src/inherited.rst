Inherited
=========

.. container:: regression

   .. lua:other-inherited-members:: inherited.Foo

   .. lua:other-inherited-members:: inherited.Baz

   .. lua:other-inherited-members:: inherited_ty.[{a: b.c}].[x.z]

   .. lua:class:: InheritedTest: inherited.Foo

      .. lua:other-inherited-members:: inherited.Baz

Targets
-------

.. lua:module:: inherited

.. lua:class:: Foo

   .. lua:data:: foo_a

   .. lua:data:: foo_b

.. lua:class:: Boo

   .. lua:data:: boo_a

   .. lua:data:: boo_b

.. lua:class:: Bar: Foo

   .. lua:data:: foo_a

   .. lua:data:: bar_c

   .. lua:data:: bar_d

.. lua:class:: Baz: Bar, Boo

   .. lua:data:: bar_d

   .. lua:data:: baz_e

.. lua:module:: inherited_ty.[{a: b.c}]

.. lua:class:: [x.y]

   .. lua:data:: [x.y.1]

   .. lua:data:: [x.y.2]

.. lua:class:: [x.z]: [x.y]

   .. lua:data:: [x.y.2]
