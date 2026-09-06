/**
 * Las formas de catálogo que el ERP repite en todas partes.
 *
 * `{ id, nombre }` estaba declarado **diecinueve veces** —`Sucursal` once,
 * `Categoria` cuatro, `Marca` tres, `Almacen` dos— y con eso vino algo peor
 * que la duplicación: pantallas importando el tipo de **otra pantalla**
 * (`import type { Proveedor } from "../ordenes-compra/ordenes-compra-cliente"`),
 * que es acoplar dos vistas por un detalle que no es de ninguna de las dos.
 * Hallazgo #15 de la auditoría del 2026-08-30.
 *
 * Acá viven solo las formas **de referencia**: lo que hace falta para
 * llenar un `<select>` o poner un nombre donde había un id. La ficha completa
 * de una sucursal —con su dirección, su tenencia y su ubicación— es otra
 * cosa y se declara donde se administra: un tipo compartido que crece con
 * cada campo que alguna pantalla necesita deja de compartir nada.
 */

/** Un id y su nombre: lo mínimo para elegir algo de una lista. */
export type Referencia = { id: string; nombre: string };

export type Sucursal = Referencia;
export type Marca = Referencia;
export type Almacen = Referencia;
export type Categoria = Referencia;
