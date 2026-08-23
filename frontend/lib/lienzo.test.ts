/**
 * Check del grafo del lienzo. Lo que se prueba es lo que puede salir mal sin
 * que nadie lo note mirando la pantalla: que las columnas salgan en el orden
 * de RN-PRD-004, que solo lo elegido alimente el plato, que una resta no
 * marcada no dibuje arista, y que el empaque distinga "no configurado" de
 * "configurado pero esta modalidad no lo consume".
 *
 * Los ayudantes que este archivo también cubre vivían dentro del componente
 * y no tenían ninguna prueba.
 *
 * Corre con `npm test`.
 */

import assert from "node:assert/strict";
import test from "node:test";

import {
  alternar,
  apilarColumna,
  armarGrafo,
  armarPartes,
  elegidosDelCamino,
  elegirEnGrupo,
  esCombinacion,
  etiquetaCorta,
  faltantesDeGrupos,
  nombreReceta,
  recetasDe,
  reglaDeGrupo,
  resolverEmpaque,
  sinVincular,
  subcolumnas,
  tituloDelPlato,
  type Camino,
  modoLegible,
  valoresExcluidos,
} from "./lienzo.ts";

function extra(id: string, nombre: string, recetaId: string | null = null) {
  return { extra_id: id, nombre, receta_id: recetaId, maximo: null };
}

function grupo(id: string, nombre: string, minimo: number, extras: unknown[]) {
  return { id, nombre, minimo, maximo: 1, orden: 0, extras };
}

function producto(over = {}) {
  return {
    id: "padre",
    id_interno: "PZZA",
    marca_id: "m",
    nombre: "Pizza",
    categoria_id: null,
    receta_id: null,
    producto_padre_id: null,
    orden: 0,
    activo: true,
    es_extra: false,
    empaque_id: null,
    modalidades_empaque: null,
    variantes: [],
    grupos: [],
    extras_sueltos: [],
    ...over,
  };
}

const SABOR = grupo("g1", "Sabor", 1, [
  extra("e1", "Peperoni", "r-pep"),
  extra("e2", "Hawaiana", "r-haw"),
]);

const FAMILIAR = producto({
  id: "fam",
  nombre: "Pizza Familiar",
  receta_id: "r-fam",
  grupos: [SABOR],
  extras_sueltos: [extra("e9", "Extra Queso", "r-queso")],
});

const CAMINO: Camino = {
  activoId: "fam",
  elegidas: { g1: ["e1"] },
  sueltos: [],
  restas: [],
  valores: [],
};

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const grafo = (over: any = {}) =>
  armarGrafo({
    padre: producto({ variantes: [] }) as never,
    variantes: [FAMILIAR] as never,
    activo: FAMILIAR as never,
    camino: CAMINO,
    recetas: [{ id: "r-fam", nombre: "Base Familiar" }] as never,
    quitables: [{ articuloId: "a1", articulo: "Orégano" }],
    empaques: [],
    modalidad: "mesa",
    disponibles: [{ id: "e7", nombre: "Extra Tocino" }],
    ...over,
  });

test("las columnas salen en el orden de RN-PRD-004", () => {
  const { nodos } = grafo();
  // Se agrupa por X y no por orden del array: el nodo del grupo comparte
  // columna con sus opciones, así que "primero Sabor y después Grupo" sería
  // una diferencia sin significado.
  const porX = new Map<number, Set<string>>();
  for (const n of nodos) {
    porX.set(n.x, (porX.get(n.x) ?? new Set()).add(n.datos.columna));
  }
  const orden = [...porX.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([, cols]) => [...cols].sort().join("+"));
  assert.deepEqual(orden, [
    "Producto",
    "Tamaño",
    "Grupo+Sabor",
    "Extras",
    "Disponibles",
    "Restas",
    "Empaque",
    "Plato",
  ]);
});

test("el grupo es un nodo, y sus opciones cuelgan de él y no del tamaño", () => {
  const { nodos, aristas } = grafo();
  const cabeza = nodos.find((n) => n.tipo === "grupo");
  assert.equal(cabeza?.id, "grupo:g1");
  assert.equal(cabeza?.datos.pie, "elige 1 · hasta 1");

  // Existe para poder colgarle cosas: es el destino de la conexión que
  // vincula un extra DENTRO del grupo.
  assert.ok(
    aristas.some((a) => a.desde === "tamano:fam" && a.hasta === "grupo:g1"),
    "el grupo cuelga del tamaño",
  );
  assert.ok(
    aristas.some((a) => a.desde === "grupo:g1" && a.hasta === "opcion:g1:e1"),
    "las opciones del grupo cuelgan del grupo",
  );
  assert.ok(
    !aristas.some((a) => a.desde === "tamano:fam" && a.hasta === "opcion:g1:e1"),
    "y NO del tamaño: si colgaran de los dos, borrar la arista sería ambiguo",
  );
});

test("el grupo obligatorio sin cumplir no se marca activo", () => {
  assert.equal(
    grafo({ camino: { ...CAMINO, elegidas: {} } })
      .nodos.find((n) => n.id === "grupo:g1")?.datos.activo,
    false,
  );
  assert.equal(
    grafo().nodos.find((n) => n.id === "grupo:g1")?.datos.activo,
    true,
  );
});

test("los extras sin vincular son nodos sueltos, sin aristas", () => {
  const { nodos, aristas } = grafo();
  const libre = nodos.find((n) => n.tipo === "disponible");
  assert.equal(libre?.id, "disponible:e7");
  assert.equal(libre?.datos.refId, "e7");
  assert.ok(
    !aristas.some((a) => a.desde === libre!.id || a.hasta === libre!.id),
    "no cuelga de nada todavía: conectarlo es lo que lo vincula",
  );
});

test("solo lo elegido alimenta el plato", () => {
  const { aristas } = grafo();
  const alPlato = aristas.filter((a) => a.hasta === "plato").map((a) => a.desde);
  assert.ok(alPlato.includes("tamano:fam"), "el tamaño activo alimenta");
  assert.ok(alPlato.includes("opcion:g1:e1"), "el sabor elegido alimenta");
  assert.ok(
    !alPlato.includes("opcion:g1:e2"),
    "el sabor NO elegido no puede alimentar el plato",
  );
});

test("una resta no marcada no dibuja arista; marcada sí y es de clase resta", () => {
  assert.equal(grafo().aristas.filter((a) => a.clase === "resta").length, 0);

  const marcada = grafo({ camino: { ...CAMINO, restas: ["a1"] } });
  const resta = marcada.aristas.find((a) => a.clase === "resta");
  assert.equal(resta?.desde, "resta:a1");
  assert.equal(resta?.hasta, "plato");
});

test("el empaque distingue no configurado de no aplica en esta modalidad", () => {
  const sinEmpaque = grafo();
  assert.equal(
    sinEmpaque.aristas.some((a) => a.desde === "empaque"),
    false,
    "sin empaque configurado no hay arista que dibujar",
  );

  const caja = { id: "caja", nombre: "Caja Pizza", costo_promedio: "0.90" };
  const conEmpaque = (modalidad: string) =>
    grafo({
      activo: { ...FAMILIAR, empaque_id: "caja", modalidades_empaque: ["delivery"] },
      empaques: [caja],
      modalidad,
    });

  assert.equal(
    conEmpaque("delivery").aristas.find((a) => a.desde === "empaque")?.clase,
    "camino",
  );
  assert.equal(
    conEmpaque("mesa").aristas.find((a) => a.desde === "empaque")?.clase,
    "inactiva",
    "en mesa el empaque existe pero no se consume (RN-EMP-003)",
  );
});

test("un producto sin tamaños es su propio nodo de tamaño", () => {
  const solo = producto({ id: "padre", receta_id: "r-fam" });
  const { nodos } = grafo({
    variantes: [],
    activo: solo,
    camino: { ...CAMINO, activoId: "padre" },
  });
  const tamanos = nodos.filter((n) => n.tipo === "tamano");
  assert.equal(tamanos.length, 1);
  assert.equal(tamanos[0].datos.titulo, "Único");
});

test("una columna que se envuelve no se monta sobre la siguiente", () => {
  // 18 disponibles se parten en 3 subcolumnas; si el índice de columna no lo
  // contempla, las restas quedan encima.
  const muchos = Array.from({ length: 18 }, (_, i) => ({
    id: `d${i}`,
    nombre: `Extra ${i}`,
  }));
  const { nodos } = grafo({ disponibles: muchos });
  const xDe = (col: string) =>
    nodos.filter((n) => n.datos.columna === col).map((n) => n.x);
  const maxDisponible = Math.max(...xDe("Disponibles"));
  const minResta = Math.min(...xDe("Restas"));
  assert.ok(
    maxDisponible < minResta,
    `disponibles llega a ${maxDisponible} y restas arranca en ${minResta}`,
  );
  assert.equal(subcolumnas(18), 3);
  assert.equal(subcolumnas(0), 1, "una columna vacía igual ocupa su lugar");
});

test("apilarColumna centra y envuelve al pasar del tope", () => {
  const tres = apilarColumna(3, 0, 100, 7);
  assert.equal(tres[1].y, 0, "el del medio queda centrado en 0");
  assert.ok(tres[0].y < 0 && tres[2].y > 0);
  assert.deepEqual(new Set(tres.map((p) => p.x)), new Set([0]));

  const nueve = apilarColumna(9, 0, 100, 7);
  assert.equal(new Set(nueve.map((p) => p.x)).size, 2, "envuelve en 2 subcolumnas");
});

// --- Ayudantes que antes vivían en el componente, sin cobertura -------------
test("un grupo obligatorio es la combinación; uno opcional son extras", () => {
  assert.equal(esCombinacion(SABOR as never), true);
  assert.equal(esCombinacion({ ...SABOR, minimo: 0 } as never), false);
  assert.equal(esCombinacion(null), false);
});

test("elegir en un grupo de un solo cupo reemplaza en vez de sumar", () => {
  const uno = elegirEnGrupo(CAMINO, SABOR as never, "e2");
  assert.deepEqual(uno.elegidas.g1, ["e2"]);

  const multi = { ...SABOR, maximo: 3 };
  const dos = elegirEnGrupo(CAMINO, multi as never, "e2");
  assert.deepEqual(dos.elegidas.g1, ["e1", "e2"]);

  const quitado = elegirEnGrupo(CAMINO, multi as never, "e1");
  assert.deepEqual(quitado.elegidas.g1, []);
});

test("faltantesDeGrupos nombra los obligatorios sin cumplir", () => {
  assert.deepEqual(faltantesDeGrupos(FAMILIAR as never, {}), ["Sabor"]);
  assert.deepEqual(faltantesDeGrupos(FAMILIAR as never, { g1: ["e1"] }), []);
});

test("sinVincular deja fuera lo que el producto ya ofrece", () => {
  const disponibles = [{ id: "e1" }, { id: "e9" }, { id: "e7" }];
  const libres = sinVincular(disponibles as never, FAMILIAR as never);
  assert.deepEqual(
    libres.map((p) => p.id),
    ["e7"],
    "e1 está en un grupo y e9 suelto: ninguno se puede volver a colgar",
  );
});

test("etiquetaCorta recorta el nombre del padre y nunca deja vacío", () => {
  assert.equal(etiquetaCorta("Pizza Familiar", "Pizza"), "Familiar");
  assert.equal(etiquetaCorta("Lasaña", "Pizza"), "Lasaña");
  assert.equal(etiquetaCorta("Pizza", "Pizza"), "Pizza");
});

test("nombreReceta distingue sin receta de receta desconocida", () => {
  assert.equal(nombreReceta([], null), "sin receta");
  assert.equal(nombreReceta([], "r-x"), "receta");
  assert.equal(nombreReceta([{ id: "r-x", nombre: "Masa" }] as never, "r-x"), "Masa");
});

test("reglaDeGrupo se lee sin saber qué es un mínimo", () => {
  assert.equal(reglaDeGrupo(SABOR as never), "elige 1 · hasta 1");
  assert.equal(
    reglaDeGrupo({ ...SABOR, minimo: 0, maximo: null } as never),
    "opcional · sin tope",
  );
});

test("resolverEmpaque no cobra el empaque en una modalidad que no lo consume", () => {
  const caja = { id: "caja", nombre: "Caja", costo_promedio: "0.90" };
  const nodo = { empaque_id: "caja", modalidades_empaque: ["delivery"] };
  assert.equal(resolverEmpaque(nodo as never, [caja] as never, "delivery").costo, 0.9);
  assert.equal(resolverEmpaque(nodo as never, [caja] as never, "mesa").costo, 0);
  assert.equal(resolverEmpaque({} as never, [] as never, "mesa").empaque, null);
});

test("armarPartes marca sabor lo obligatorio y extra lo opcional", () => {
  const elegidos = elegidosDelCamino(FAMILIAR as never, { g1: ["e1"] }, ["e9"]);
  const partes = armarPartes(FAMILIAR as never, "Pizza", elegidos, {});
  assert.deepEqual(
    partes.map((p) => p.tipo),
    ["tamano", "sabor", "extra"],
  );
  assert.equal(partes[0].titulo, "Familiar");
});

test("recetasDe no repite ni incluye nulos", () => {
  const elegidos = elegidosDelCamino(FAMILIAR as never, { g1: ["e1"] }, ["e9"]);
  assert.deepEqual(recetasDe(FAMILIAR as never, elegidos), [
    "r-fam",
    "r-pep",
    "r-queso",
  ]);
  const sinReceta = elegidosDelCamino(
    { ...FAMILIAR, extras_sueltos: [extra("e8", "Sin receta")] } as never,
    {},
    ["e8"],
  );
  assert.deepEqual(recetasDe({ ...FAMILIAR, receta_id: null } as never, sinReceta), []);
});

test("tituloDelPlato lista lo agregado tras el nombre", () => {
  const elegidos = elegidosDelCamino(FAMILIAR as never, { g1: ["e1"] }, ["e9"]);
  const partes = armarPartes(FAMILIAR as never, "Pizza", elegidos, {});
  assert.equal(
    tituloDelPlato(FAMILIAR as never, producto() as never, partes),
    "Pizza Familiar · Peperoni, Extra Queso",
  );
});

test("alternar agrega y quita sin mutar", () => {
  const base = ["a"];
  assert.deepEqual(alternar(base, "b"), ["a", "b"]);
  assert.deepEqual(alternar(base, "a"), []);
  assert.deepEqual(base, ["a"]);
});

// --- Atributos en el lienzo (ADR-055, ADR-058) -----------------------------

test("una exclusión se lee en los dos sentidos", () => {
  // Se guarda una sola fila porque el par es simétrico (RN-COM-038), así que
  // hay que mirar las dos puntas.
  assert.deepEqual([...valoresExcluidos(["a"], [["a", "b"]])], ["b"]);
  assert.deepEqual([...valoresExcluidos(["b"], [["a", "b"]])], ["a"]);
});

test("lo elegido no se apaga a sí mismo", () => {
  // Si no, elegir algo lo tacharía en el mismo click.
  assert.deepEqual([...valoresExcluidos(["a", "b"], [["a", "b"]])], []);
});

test("sin nada elegido no hay nada apagado", () => {
  assert.equal(valoresExcluidos([], [["a", "b"]]).size, 0);
});

test("el modo de variante se dice sin jerga", () => {
  assert.match(modoLegible("siempre"), /variante/);
  assert.equal(modoLegible("nunca"), "no genera variantes");
  // Un modo que no conocemos no rompe la pantalla.
  assert.equal(modoLegible("otro"), "no genera variantes");
});

