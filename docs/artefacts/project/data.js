// Sample content for Comprende Ya
// B2 Spanish — natural register, with a fictional documentary-style episode.

window.LIBRARY = [
  {
    id: 'mercados',
    title: 'Lo que los mercados de barrio nos enseñan',
    channel: 'Voces de la ciudad',
    duration: '14:32',
    level: 'B2',
    progress: 0.42,
    tags: ['documental', 'cultura urbana'],
    color: 'oklch(0.78 0.06 55)',
    pattern: 'a',
  },
  {
    id: 'sobremesa',
    title: 'La sobremesa: por qué no nos levantamos',
    channel: 'Cosas de aquí',
    duration: '09:48',
    level: 'B2',
    progress: 1.0,
    tags: ['cultura', 'entrevista'],
    color: 'oklch(0.82 0.05 95)',
    pattern: 'b',
  },
  {
    id: 'lluvia',
    title: 'Madrid bajo la lluvia (caminata)',
    channel: 'Paseos sonoros',
    duration: '22:10',
    level: 'B2',
    progress: 0,
    tags: ['paseo', 'descripción'],
    color: 'oklch(0.74 0.04 230)',
    pattern: 'c',
  },
  {
    id: 'cafe',
    title: 'Cómo se pide un café (sin equivocarse)',
    channel: 'Español a pie de calle',
    duration: '06:21',
    level: 'B1',
    progress: 0,
    tags: ['práctico', 'pronunciación'],
    color: 'oklch(0.80 0.07 70)',
    pattern: 'd',
  },
  {
    id: 'vecindad',
    title: 'Una conversación con mi vecina',
    channel: 'Voces de la ciudad',
    duration: '11:05',
    level: 'B2',
    progress: 0.18,
    tags: ['entrevista', 'coloquial'],
    color: 'oklch(0.76 0.05 25)',
    pattern: 'e',
  },
  {
    id: 'sur',
    title: 'El silencio del sur',
    channel: 'Paseos sonoros',
    duration: '17:54',
    level: 'C1',
    progress: 0,
    tags: ['narrativa', 'lento'],
    color: 'oklch(0.72 0.04 145)',
    pattern: 'f',
  },
];

// Transcript for the active episode "Lo que los mercados de barrio nos enseñan"
// Each segment has a start time, speaker, and an array of tokens.
// Tokens: {t: 'word'} or {t: 'word', w: true} for "interesting" (tappable for autopsy).
// Punctuation tokens: {p: ','}.
window.TRANSCRIPT = [
  {
    id: 's1',
    start: 0,
    end: 14,
    speaker: 'Narradora',
    autopsy: { phrase: 'a eso de las nueve', words: ['a','eso','de','las','nueve'] },
    tokens: [
      { t: 'Mira' }, { p: ',' }, { t: 'lo' }, { t: 'que' }, { t: 'pasa' },
      { t: 'en' }, { t: 'un' }, { t: 'mercado' }, { t: 'de' }, { t: 'barrio' },
      { p: ',' }, { t: 'a' }, { t: 'eso' }, { t: 'de' }, { t: 'las' },
      { t: 'nueve' }, { t: 'de' }, { t: 'la' }, { t: 'mañana' }, { p: ',' },
      { t: 'no' }, { t: 'lo' }, { t: 'ves' }, { t: 'en' }, { t: 'ningún' },
      { t: 'otro' }, { t: 'sitio' }, { p: '.' },
    ],
  },
  {
    id: 's2',
    start: 14,
    end: 32,
    speaker: 'Narradora',
    tokens: [
      { t: 'La' }, { t: 'gente' }, { t: 'se' }, { t: 'saluda' },
      { t: 'por' }, { t: 'el' }, { t: 'nombre' }, { p: ',' },
      { t: 'se' }, { t: 'pregunta' }, { t: 'por' }, { t: 'los' },
      { t: 'hijos' }, { p: ',' }, { t: 'y' }, { t: 'de' }, { t: 'paso' },
      { p: ',' }, { t: 'compran' }, { t: 'tomates' }, { p: '.' },
    ],
  },
  {
    id: 's3',
    start: 32,
    end: 54,
    speaker: 'Carmen, frutera',
    autopsy: { phrase: 'no me da igual', words: ['no','me','da','igual'] },
    tokens: [
      { t: 'Yo' }, { t: 'llevo' }, { t: 'aquí' }, { t: 'cuarenta' },
      { t: 'años' }, { p: ',' }, { t: 'fíjate' }, { p: '.' },
      { t: 'A' }, { t: 'mí' }, { t: 'no' }, { t: 'me' }, { t: 'da' },
      { t: 'igual' }, { t: 'a' }, { t: 'quién' }, { t: 'le' },
      { t: 'vendo' }, { t: 'una' }, { t: 'manzana' }, { p: '.' },
    ],
  },
  {
    id: 's4',
    start: 54,
    end: 78,
    speaker: 'Carmen, frutera',
    tokens: [
      { t: 'Es' }, { t: 'que' }, { t: 'la' }, { t: 'conozco' }, { p: ',' },
      { t: '¿sabes?' }, { t: 'Y' }, { t: 'si' }, { t: 'un' }, { t: 'día' },
      { t: 'no' }, { t: 'viene' }, { p: ',' }, { t: 'pues' }, { t: 'me' },
      { t: 'preocupo' }, { p: '.' }, { t: 'Eso' }, { t: 'en' }, { t: 'el' },
      { t: 'súper' }, { t: 'no' }, { t: 'lo' }, { t: 'tienes' }, { p: '.' },
    ],
  },
];

// Comprehension question that fires after segment s2 finishes
window.QUESTIONS = [
  {
    afterSegment: 's2',
    prompt: 'Según la narradora, ¿qué hace la gente además de comprar?',
    choices: [
      { id: 'a', text: 'Discuten sobre los precios.' },
      { id: 'b', text: 'Se saludan y preguntan por la familia.' },
      { id: 'c', text: 'Llaman a sus hijos por teléfono.' },
      { id: 'd', text: 'Esperan en silencio su turno.' },
    ],
    correct: 'b',
    explain: '«Se saludan por el nombre, se pregunta por los hijos» — el mercado funciona también como red social del barrio.',
  },
  {
    afterSegment: 's4',
    prompt: '¿Por qué dice Carmen que no le da igual a quién le vende?',
    choices: [
      { id: 'a', text: 'Porque cobra precios distintos a cada cliente.' },
      { id: 'b', text: 'Porque conoce a sus clientes y se preocupa por ellos.' },
      { id: 'c', text: 'Porque quiere vender más fruta.' },
      { id: 'd', text: 'Porque trabaja sola y necesita compañía.' },
    ],
    correct: 'b',
    explain: '«La conozco… si un día no viene, pues me preocupo». La relación es personal, no transaccional.',
  },
];

// Autopsy data — keyed by phrase text
window.AUTOPSY = {
  'a eso de las nueve': {
    natural: 'around nine-ish',
    literal: 'at that of the nine',
    grammar: [
      { tag: 'preposición', text: '«a» marca la hora puntual.' },
      { tag: 'pronombre demostrativo neutro', text: '«eso» se refiere de forma vaga a un punto en el tiempo, no a un objeto concreto.' },
      { tag: 'partitivo «de»', text: 'introduce el referente: «de las nueve».' },
    ],
    natural_notes: [
      'Suena más natural que «a las nueve» cuando la hora es aproximada.',
      'Si dijeras «a las nueve en punto», el oyente esperaría exactitud. Aquí la hablante no la promete.',
      'Es muy común en habla cotidiana; en un parte de noticias casi nunca lo oirías.',
    ],
    register: 'cotidiano · neutral',
  },
  'no me da igual': {
    natural: "I do care / it isn't all the same to me",
    literal: 'it does not give me equal',
    grammar: [
      { tag: 'verbo «dar» impersonal', text: '«dar igual» funciona como una sola unidad — el sujeto gramatical es la cosa que importa o no, no la persona.' },
      { tag: 'pronombre dativo «me»', text: 'señala a quién le importa («a mí»). Por eso la frase a veces empieza con «A mí no me da igual…».' },
      { tag: 'negación', text: 'el «no» antes del clítico es la posición fija; no se dice «me no da igual».' },
    ],
    natural_notes: [
      'En contexto, esta forma negada es enfática: Carmen no está siendo neutral, está reivindicando que sí le importa.',
      'Un libro de texto traduciría «no me importa», pero en habla real «no me da igual» suena más cálido y menos formal.',
      'Suele ir seguido de un «¿eh?» o «¿sabes?» de cierre, como confirma la siguiente línea.',
    ],
    register: 'cotidiano · enfático',
  },
};

// Chunk library — phrases the user has saved, with practice prompts
window.CHUNKS = [
  {
    id: 'c1',
    phrase: 'a eso de las nueve',
    gloss: 'around nine-ish',
    source: 'Lo que los mercados de barrio nos enseñan',
    saved: '2 days ago',
    mastery: 0.4,
    prompts: [
      'Di a qué hora sueles desayunar usando «a eso de…».',
      'Cuenta a qué hora llegaste ayer a casa, sin dar la hora exacta.',
      'Describe cuándo empieza tu programa favorito.',
    ],
  },
  {
    id: 'c2',
    phrase: 'no me da igual',
    gloss: "I do care about it",
    source: 'Lo que los mercados de barrio nos enseñan',
    saved: 'Today',
    mastery: 0.15,
    prompts: [
      'Piensa en algo que la gente cree que no te importa, pero sí. Empieza con «A mí no me da igual…».',
      'Contradice a alguien que dijo: «Da igual cómo lo hagamos».',
    ],
  },
  {
    id: 'c3',
    phrase: 'fíjate',
    gloss: 'check this out / mind you',
    source: 'Lo que los mercados de barrio nos enseñan',
    saved: 'Today',
    mastery: 0.6,
    prompts: [
      'Cuenta un dato sorprendente sobre tu ciudad, abriendo con «Fíjate que…».',
      'Llama la atención de alguien sobre algo que ves por la ventana.',
    ],
  },
  {
    id: 'c4',
    phrase: 'de paso',
    gloss: 'while we’re at it / on the way',
    source: 'Lo que los mercados de barrio nos enseñan',
    saved: 'Yesterday',
    mastery: 0.55,
    prompts: [
      'Describe un recado que aprovechaste para hacer otra cosa.',
      'Sugiere a un amigo que pase a comprar pan «de paso».',
    ],
  },
  {
    id: 'c5',
    phrase: 'pues',
    gloss: 'well… / so…',
    source: 'La sobremesa: por qué no nos levantamos',
    saved: '3 days ago',
    mastery: 0.75,
    prompts: [
      'Responde a la pregunta «¿qué tal el día?» empezando con «Pues…».',
      'Dúdalo en voz alta antes de tomar una decisión.',
    ],
  },
  {
    id: 'c6',
    phrase: '¿sabes?',
    gloss: 'you know?',
    source: 'Lo que los mercados de barrio nos enseñan',
    saved: '1 week ago',
    mastery: 0.5,
    prompts: [
      'Termina una frase tuya con «¿sabes?» para buscar complicidad.',
      'Cuenta una opinión personal y ciérrala con esta muletilla.',
    ],
  },
];
