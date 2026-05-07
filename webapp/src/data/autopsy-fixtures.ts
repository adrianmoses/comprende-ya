import type { AutopsyEntry } from "../lib/autopsy-types";

const FIXTURES: Record<string, Record<string, AutopsyEntry>> = {
	m1DFpkNdcv0: {
		"a eso de las nueve": {
			phrase: "a eso de las nueve",
			start_time: 12,
			register: "cotidiano · neutral",
			grammar: [
				{
					tag: "preposición",
					text: "«a» marca la hora puntual.",
				},
				{
					tag: "demostrativo neutro",
					text: "«eso» se refiere de forma vaga a un punto en el tiempo, no a un objeto concreto.",
				},
				{
					tag: "partitivo «de»",
					text: "introduce el referente: «de las nueve».",
				},
			],
			natural_notes: [
				"Suena más natural que «a las nueve» cuando la hora es aproximada.",
				"Si dijeras «a las nueve en punto», el oyente esperaría exactitud. Aquí la hablante no la promete.",
				"Es muy común en habla cotidiana; en un parte de noticias casi nunca lo oirías.",
			],
		},
		"no me da igual": {
			phrase: "no me da igual",
			start_time: 96,
			register: "cotidiano · enfático",
			grammar: [
				{
					tag: "verbo «dar» impersonal",
					text: "«dar igual» funciona como una sola unidad — el sujeto gramatical es la cosa que importa o no, no la persona.",
				},
				{
					tag: "pronombre dativo «me»",
					text: "señala a quién le importa («a mí»). Por eso la frase a veces empieza con «A mí no me da igual…».",
				},
				{
					tag: "negación",
					text: "el «no» antes del clítico es la posición fija; no se dice «me no da igual».",
				},
			],
			natural_notes: [
				"En contexto, esta forma negada es enfática: la hablante no está siendo neutral, está reivindicando que sí le importa.",
				"Un libro de texto traduciría «no me importa», pero en habla real «no me da igual» suena más cálido y menos formal.",
				"Suele ir seguido de un «¿eh?» o «¿sabes?» de cierre.",
			],
		},
	},
};

export function getAutopsyEntries(youtubeId: string): Array<AutopsyEntry> {
	const byPhrase = FIXTURES[youtubeId];
	if (!byPhrase) return [];
	return Object.values(byPhrase);
}

export function getAutopsyEntry(
	youtubeId: string,
	phrase: string,
): AutopsyEntry | null {
	return FIXTURES[youtubeId]?.[phrase] ?? null;
}
