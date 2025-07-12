Inherited
=========

.. lua:module:: inherited

.. lua:class:: Foo

   .. lua:data:: foo_a

   .. lua:data:: foo_b

.. lua:class:: Bar: Foo

   .. lua:data:: foo_a

   .. lua:data:: bar_c

   .. lua:data:: bar_d

.. lua:class:: Baz: Bar

   .. lua:data:: bar_d

   .. lua:data:: baz_e

.. container:: regression

   .. lua:inherited-members:: inherited.Baz
