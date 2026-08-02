# SOP — Publicación de convocatoria

**Área:** Recursos Humanos · **Grupo:** Reclutamiento

## Objetivo
Atraer postulantes adecuados en pocos días, con un aviso claro y legal — un
aviso discriminatorio expone a multa (Ley 26772) y espanta buenos candidatos.

## Frecuencia
Al aprobarse una requisición de personal.

## Responsable
Administrador/gerente.

## Materiales y equipo
- Requisición aprobada + perfil de puesto
- Plantilla: [convocatoria-puesto](../../../../templates/rrhh/convocatoria-puesto.md)
- ERP: módulo RRHH → Convocatorias (crear, publicar, cerrar)
- Formulario de postulación en **Google Forms** conectado al ERP (ver abajo)
- Canales: grupos de Facebook de empleo de la zona, Computrabajo/Indeed,
  cartel en el local, referidos del personal actual

## Pasos
1. Registrar la convocatoria en el ERP desde la requisición aprobada: puesto,
   sucursal, motivo, vacantes, jornada, rango salarial y fecha límite. Queda
   en **borrador**.
2. Redactar el aviso con la plantilla, partiendo del perfil: puesto, marca y
   zona de la sucursal, funciones resumidas (3-4), requisitos reales, jornada
   y turnos, y qué ofrece la empresa (sueldo o rango, uniforme, capacitación).
3. Revisar que NO contenga requisitos discriminatorios: edad, sexo, "buena
   presencia", estado civil, foto, religión. Pedir solo lo que el puesto exige.
   **El ERP no puede revisar esto: lo revisa el administrador antes de
   publicar** (RN-RRHH-013).
4. Publicar la convocatoria en el ERP. Sin perfil de puesto registrado el
   sistema la rechaza. Al publicar, el ERP entrega el **token** del formulario.
5. Duplicar el Google Form modelo, pegar el token en su Apps Script (abajo) y
   poner el enlace del formulario como canal único de postulación en el aviso,
   junto con la fecha límite.
6. Publicar el aviso en mínimo 2 canales: referidos internos + 1 canal público.
   Avisar al personal actual — un referido de un buen trabajador suele ser
   el mejor canal.
7. Al postular, cada persona indica en el formulario **cómo se enteró**: es lo
   que después permite comparar canal vs. contratado final.
8. Cerrar la convocatoria en el ERP en la fecha límite o al juntar suficientes
   postulantes filtrables (referencia: 8-10 CVs para un puesto operativo).
   Cerrar desactiva el formulario; los postulantes ya recibidos siguen su
   proceso en el tablero.

## Conexión del formulario con el ERP

Google Forms es el formulario porque es gratis, el candidato ya sabe usarlo
desde el celular y no hay nada que hospedar. El puente al ERP es un Apps
Script del propio formulario (**Extensiones → Apps Script**), con un
disparador `onFormSubmit`:

```javascript
const TOKEN = 'PEGAR-AQUI-EL-TOKEN-DE-LA-CONVOCATORIA';
const URL = 'https://<dominio-del-erp>/api/v1/rrhh/postulaciones/' + TOKEN;

function alEnviarFormulario(e) {
  const r = {};
  e.response.getItemResponses().forEach(ir => {
    r[ir.getItem().getTitle()] = String(ir.getResponse());
  });
  UrlFetchApp.fetch(URL, {
    method: 'post',
    contentType: 'application/json',
    payload: JSON.stringify({
      nombres: r['Nombres'],
      apellidos: r['Apellidos'],
      telefono: r['Teléfono'],
      email: r['Correo'],
      canal_origen: r['¿Cómo se enteró?'],
      consentimiento_datos: r['Autorizo el tratamiento de mis datos'] === 'Sí',
      respuestas: r,
    }),
  });
}
```

El formulario debe incluir sí o sí la pregunta de autorización de datos
(obligatoria, opciones Sí/No): sin consentimiento el ERP rechaza la
postulación (RN-PER-004, Ley 29733). Las demás preguntas son libres — se
guardan tal cual y se ven en la ficha del postulante.

Si el token cambia (convocatoria nueva), se actualiza la constante `TOKEN` del
script del formulario duplicado. Un token de una convocatoria cerrada deja de
funcionar solo.

## Excepciones
- Si en 5 días no llegan postulantes → revisar sueldo ofrecido contra mercado
  de la zona y reescribir el aviso antes de re-publicar; no bajar requisitos
  de sanidad ni disponibilidad.
- Si el puesto es urgente → priorizar referidos y ex-trabajadores de temporada
  con buen historial; la publicación pública corre en paralelo.

## Problemas frecuentes
| Síntoma | Causa | Corrección |
|---|---|---|
| Llegan CVs que no tienen nada que ver | Aviso vago ("se busca personal") | Usar la plantilla: puesto, funciones y turnos explícitos |
| Nadie postula | Sueldo bajo mercado o canal equivocado | Comparar con avisos similares de la zona; cambiar canal |
| Aviso pide "señorita hasta 25 años" | Costumbre local, es ilegal | Paso 2 es obligatorio; el administrador revisa antes de publicar |

## Checklist de verificación
- [ ] Convocatoria registrada en el ERP con perfil de puesto
- [ ] Aviso redactado desde el perfil con la plantilla
- [ ] Sin requisitos discriminatorios
- [ ] Convocatoria publicada en el ERP y token pegado en el formulario
- [ ] Enlace del formulario y fecha límite en el aviso
- [ ] Publicado en ≥ 2 canales (incluye referidos internos)
- [ ] Convocatoria cerrada en fecha límite

## Evidencia y supervisión
Captura o enlace de cada publicación en el expediente de la búsqueda. El
`canal_origen` de cada postulante queda en el ERP: el administrador compara
canal vs. contratado final para invertir mejor la siguiente vez.
