from typing import List, Dict, Tuple
import random
import spacy

from models.database import VideoSegment


class FraseExerciseGeneratorService:
    """Servicio para generar frases exercicios de fill-in-the-blank"""

    def __init__(self, difficulty: str = "medio"):
        spacy.prefer_gpu()
        self.nlp = spacy.load("es_dep_news_trf")
        self.difficulty = difficulty

        # Configuración por nivel de dificultad
        self.config = {
            "facil": {
                "num_blanks": (1, 2),  # 1-2 blanks por frase
                "pos_tags": ["VERB", "PRON"]  # Solo verbos y sustantivos
            },
            "medio": {
                "num_blanks": (2, 4),  # 2-4 blanks por frase
                "pos_tags": ["VERB", "PRON", "ADP"]  # + preposiciones y adjetivos
            },
            "dificil": {
                "num_blanks": (3, 6),  # 3-6 blanks por frase
                "pos_tags": ["VERB", "ADP", "PRON", "SCONJ", "CCONJ"]  # Todas las categorías
            }
        }

    def select_words_to_blank(self, frase: str) -> List[Tuple[int, str]]:
        """
        Retorna lista de (indice_token, palabra_original) para convertir en blanks
        """
        doc = self.nlp(frase)
        config = self.config[self.difficulty]

        candidates = []

        for i, token in enumerate(doc):
            # Criterios de selección
            if self._is_good_candidate(token, config["pos_tags"]):
                candidates.append((i, token.text, token.pos_, self._get_priority(token)))

        # Ordenar por prioridad y selccionar
        candidates.sort(key=lambda x: x[3], reverse=True)

        min_blanks, max_blanks = config["num_blanks"]
        num_blanks = min(random.randint(min_blanks, max_blanks), len(candidates))

        selected = candidates[:num_blanks]
        return [(idx, word) for idx, word, _, _ in selected]

    def _is_good_candidate(self, token, allowed_pos: List[str]) -> bool:
        """Determina si un token es buen candidato para blank"""

        # Debe estar en las categories permitidas
        if token.pos_ not in allowed_pos:
            return False

        # Excluir tokens muy cortos (artículos, etc.)
        if len(token.text) <= 2 and token.pos_ not in ["VERB", "PRON"]:
            return False

        # Excluir puntuación
        if token.is_punct:
            return False

        return True

    def _get_priority(self, token) -> int:
        """Asigna prioridad a tokens - más alto = más importante practicar"""
        priority = 0

        # ALTA PRIORIDAD: Verbos reflexivos
        if token.pos_ == "PRON" and token.dep_ == "expl":
            priority += 10

        # ALTA PRIORIDAD: Verbos en tiempos complejos
        if token.pos_ == "VERB":
            if "Subjuntive" in token.morph.get("Mood", []):
                priority += 8
            elif "Past" in token.morph.get("Tense", []):
                priority += 6
            else:
                priority += 5


        # MEDIA PRIORIDAD: Preposiciones dificles
        if token.pos_ == "ADP":
            if token.text in ["por", "para", "a"]:
                priority += 7
            else:
                priority += 4


        # MEDIA PRIORIDAD: Pronombres objeto
        if token.pos_ == "PRON" and token.dep_ in ["obj", "iobj"]:
            priority += 6

        # MEDIA PRIORIDAD: Conectores
        if token.pos_ in ["SCONJ", "CCONJ"]:
            if token.text in ["que", "aunque", "si", "porque"]:
                priority += 5

        return priority


    def create_exercise(self, frase: str) -> Dict:
        """Genera una frase exercicio completo con blanks"""
        doc = self.nlp(frase)
        blanks = self.select_words_to_blank(frase)

        blank_dict = {idx: word for idx, word in blanks}


        tokens_with_blanks = []
        for i, token in enumerate(doc):
            if i in blank_dict:
                tokens_with_blanks.append("___")
            else:
                tokens_with_blanks.append(token.text_with_ws)

        frases_con_blanks = "".join(tokens_with_blanks).strip()

        return {
            "original_transcript_text": frase,
            "exercise_text": frases_con_blanks,
            "answers": {f"blank_{i}": word for i, (idx, word) in enumerate(blanks)},
            "hints": self._generate_hints(doc, blank_dict)
        }


    def _generate_hints(self, doc, blank_dict: Dict[int, str]) -> Dict:

        hints = {}
        for i, (idx, word) in enumerate(blank_dict.items()):
            token = doc[idx]
            hint_parts = []

            if token.pos_ == "VERB":
                hint_parts.append("verbo")
                if "Subjunctive" in token.morph.get("Mood", []):
                    hint_parts.append(f"subjuntivo")
            elif token.pos_ == "ADP":
                hint_parts.append("preposición")
            elif token.pos_ == "PRON":
                hint_parts.append("pronombre")

            hints[f"blank_{i}"] = " - ".join(hint_parts) if hint_parts else "palabra funcional"

        return hints

    def generate_exercises_from_transcription(self,
                                              transcription_segments: List[VideoSegment],
                                              sample_rate: float = 0.1 # 10% de frases
                                              ) -> List[Dict]:
        """
        Genera ejercicios de fill-in-the-blank desde segmentos de transcription.

        Args:
            transcription_segments: Lista de {text, start_time, end_time}
            difficulty: facio/medio/dificil
            sample_rate: Porcentaje de frases a convertir en ejercicios
        """

        # Randomly sample segments based on sample_rate
        num_to_sample = max(1, int(len(transcription_segments) * sample_rate))
        sampled_segments: List[VideoSegment] = random.sample(transcription_segments, min(num_to_sample, len(transcription_segments)))

        frase_exercises = []
        for segment in sampled_segments:
            frase_exercise_dict = self.create_exercise(segment.transcript_text)
            frase_exercise_dict['start_time'] = segment.start_time
            frase_exercise_dict['end_time'] = segment.end_time
            frase_exercise_dict['difficulty'] = self.difficulty
            frase_exercises.append(frase_exercise_dict)

        return frase_exercises


