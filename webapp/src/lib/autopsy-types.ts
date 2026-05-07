export type AutopsyGrammarRow = {
	tag: string;
	text: string;
};

export type AutopsyEntry = {
	phrase: string;
	start_time: number;
	register: string;
	grammar: Array<AutopsyGrammarRow>;
	natural_notes: Array<string>;
};

export type AutopsyTarget = {
	phrase: string;
	segmentNumber: number | null;
};
