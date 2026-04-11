from anthropic import Anthropic
from config import settings
from models.schemas import Question, TimestampedQuestion, DetailedTranscript
import re
import json

class QuestionService:

    def __init__(self):
        self.client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    def _extract_json(self, text: str) -> str:
        """Extrae JSON de bloques markdown"""
        text = text.strip()

        json_block_match = re.search(
            r'```json\s*([\s\S]*?)\s*```',
            text,
            re.MULTILINE
        )
        if json_block_match:
            return json_block_match.group(1).strip()

        # Patrón 2: Buscar JSON dentro de ``` ... ``` (sin especificar lenguaje)
        code_block_match = re.search(
            r'```\s*([\s\S]*?)\s*```',
            text,
            re.MULTILINE
        )
        if code_block_match:
            potential_json = code_block_match.group(1).strip()
            # Verificar que empiece con [ o {
            if potential_json.startswith('[') or potential_json.startswith('{'):
                return potential_json

        # Patrón 3: Buscar array JSON directamente (sin bloques de código)
        # Buscar desde el primer [ hasta el último ] balanceado
        array_match = re.search(
            r'(\[\s*\{[\s\S]*\}\s*\])',
            text
        )
        if array_match:
            return array_match.group(1).strip()

        # Patrón 4: Buscar objeto JSON directamente
        object_match = re.search(
            r'(\{\s*"[\s\S]*\})',
            text
        )
        if object_match:
            return object_match.group(1).strip()

        return text.strip()

    def _validate_and_parse_json(self, text: str) -> list:
        """
        Valida y parsea JSON, con mejor manejo de errores
        """
        json_text = self._extract_json(text)

        try:
            data = json.loads(json_text)

            # Validar que sea una lista
            if not isinstance(data, list):
                raise ValueError(f"Esperaba una lista, recibió: {type(data).__name__}")

            return data

        except json.JSONDecodeError as e:
            # Intentar limpiar caracteres problemáticos comunes
            cleaned = json_text.replace('\n', ' ').replace('\r', '')

            try:
                data = json.loads(cleaned)
                if not isinstance(data, list):
                    raise ValueError(f"Esperaba una lista, recibió: {type(data).__name__}")
                return data
            except:
                # Si aún falla, mostrar más contexto
                raise ValueError(
                    f"No se pudo parsear JSON.\n"
                    f"Error: {str(e)}\n"
                    f"Texto extraído (primeros 500 chars): {json_text[:500]}\n"
                    f"Respuesta completa de Claude (primeros 1000 chars): {text[:1000]}"
                )


    def generate_timestamped_questions(self,
                                       detailed_transcript: DetailedTranscript,
                                       num_questions: int = 5) -> list[TimestampedQuestion]:
        """
        Genera preguntas con timestamps basadas en segmentos
        :param detailed_transcript:
        :param num_questions:
        :return:
        """

        # Sample segments evenly from different parts of the video for better distribution
        segments = detailed_transcript.segments
        total_duration = detailed_transcript.duration

        # Divide video into sections (one per question)
        section_duration = total_duration / num_questions
        sampled_segments = []

        for i in range(num_questions):
            # Define the time range for this section
            section_start = i * section_duration
            section_end = (i + 1) * section_duration

            # Find segments that fall within this section
            section_segments = [
                seg for seg in segments
                if section_start <= seg.start < section_end
            ]

            # Add all segments from this section (to give Claude context)
            sampled_segments.extend(section_segments)

        # If we didn't get enough segments (edge case), use all segments
        if len(sampled_segments) < num_questions:
            sampled_segments = segments

        # Create context with timestamps for Claude
        segments_text = "\n".join([
            f"[{seg.start:.1f}s - {seg.end:.1f}s]: {seg.text}"
            for seg in sampled_segments
        ])

        prompt = f"""Basándote en esta transcripción con timestamps, genera {num_questions} preguntas de comprensión.

        Duración total del video: {detailed_transcript.duration:.1f} segundos

        IMPORTANTE - DISTRIBUCIÓN: El video ha sido dividido en {num_questions} secciones temporales.
        Debes generar EXACTAMENTE UNA pregunta para CADA sección, distribuyéndolas uniformemente:
        {chr(10).join([f"- Sección {i+1}: {i * section_duration:.1f}s - {(i+1) * section_duration:.1f}s" for i in range(num_questions)])}

        Transcripción con timestamps (organizada por secciones):
        {segments_text}

        TIPOS DE PREGUNTAS (en orden de prioridad):
        1. EXPRESIONES COLOQUIALES (40%): Identifica modismos, frases hechas, y expresiones idiomáticas.
           - Pregunta sobre su significado en contexto
           - Incluye suficiente contexto para inferir
           - Ejemplo: "Cuando dice 'se quedó de piedra', ¿qué significa sobre su reacción?"

        2. COMPRENSIÓN DE IDEAS (30%): Testea si entendieron el argumento o punto principal
           - No solo memoria de palabras específicas
           - Ejemplo: "¿Por qué el presentador cree que X es importante?"

        3. VOCABULARIO EN CONTEXTO (30%): Palabras menos comunes o técnicas
           - Testea comprensión del significado, no traducción
           - Ejemplo: "¿A qué se refiere con 'desfase'?"

        EVITA:
        - Preguntas sobre números exactos o detalles triviales
        - Preguntas que requieran memoria fotográfica
        - Preguntas cuya respuesta sea una sola palabra sin contexto

        TIMING:
        1. El timestamp debe ser el momento EXACTO donde termina de mencionarse la información
        2. Si la información se menciona entre 15.0s y 17.5s, usa timestamp: 17.5
        3. Esto asegura que la pregunta aparezca DESPUÉS de escuchar el contenido completo
        4. Asegúrate que cada pregunta tenga un timestamp dentro de su sección correspondiente

        Responde ÚNICAMENTE con un array JSON (sin markdown):
        [
          {{
            "timestamp": 15.5,
            "question": "¿Qué significa cuando dice...?",
            "answers": ["Opción A", "Opción B", "Opción C", "Opción D"],
            "correct_answer": 0,
            "explanation": "La respuesta es A porque la expresión 'X' significa...",
            "question_type": "colloquial" // o "comprehension" o "vocabulario"
          }}
        ]
        """

        # prompt = f"""Basándote en esta transcripción con timestamps, genera {num_questions} preguntas de comprensión.
        #
        # Duración total del video: {detailed_transcript.duration:.1f} segundos
        #
        # Transcripción con timestamps:
        # {segments_text}
        #
        # IMPORTANTE:
        # 1. Distribuye las preguntas a lo largo del video (no todas al principio)
        # 2. El timestamp debe ser el momento EXACTO donde termina de mencionarse la información
        # 3. Si la información se menciona entre 15.0s y 17.5s, usa timestamp: 17.5
        # 4. Esto asegura que la pregunta aparezca DESPUÉS de escuchar el contenido completo
        # 5. Las preguntas deben ser sobre información específica mencionada en ese momento
        #
        # Responde ÚNICAMENTE con un array JSON (sin markdown):
        # [
        #   {{
        #     "timestamp": 15.5,
        #     "question": "¿Qué acaba de mencionar sobre...?",
        #     "answers": ["Opción A", "Opción B", "Opción C", "Opción D"],
        #     "correct_answer": 0,
        #     "explanation": "La respuesta es A porque en este momento del video se menciona..."
        #   }}
        # ]
        #
        # """

        message = self.client.messages.create(
            model="claude-4-sonnet-20250514",
            max_tokens=2500,
            messages=[{
                "role": "user",
                "content": prompt,
            }]
        )

        # Extraer y parsear JSON
        response_text = message.content[0].text
        # Debug: imprimir respuesta
        print(f"\n{'='*60}")
        print("RESPUESTA DE CLAUDE:")
        print(f"{'='*60}")
        print(response_text[:500])
        print(f"{'='*60}\n")

        # Parsear con validación
        questions_data = self._validate_and_parse_json(response_text)

        # Convertir a objetos TimestampedQuestion
        questions = []
        for i, q in enumerate(questions_data):
            try:
                questions.append(TimestampedQuestion(**q))
            except Exception as e:
                raise ValueError(f"Error en pregunta {i+1}: {e}. Datos: {q}")

        # Ordernar por timestamp
        questions.sort(key=lambda q: q.timestamp)

        return questions


    def generate_question(self, transcript: str, num_questions: int = 5) -> list[Question]:
        """
        Genera preguntas de comprensión usando Claude
        :param transcript:
        :param num_questions:
        :return:
        """
        try:
            prompt = f"""
            Basándote en esta transcripción en español, genera {num_questions} preguntas de comprensión
            de opción múltiple.
            
            Transcripción:
            {transcript}
            
            Para cada pregunta, proporciona:
            1. La pregunta
            2. 4 opciones de respuesta
            3. El índice (0-3) de la respuesta correcta
            4. Una breve explicación
            
            Responde SOLO con una JSON válido en este formato:
            
            [
              {{
                "question": "¿Cuál es...?",
                "answers": ["Opción A", "Opción B", "Opción C", "Opción D"],
                "correct_answer": 0,
                "explanation": "La respuesta correcta es A porque..."
              }}
            ]
            """

            message = self.client.messages.create(
                model="claude-4-sonnet-20250514",
                max_tokens=2000,
                messages=[{
                    "role": "user",
                    "content": prompt,
                }]
            )

            # Parsear respuesta JSON
            response_text = message.content[0].text
            json_text = self._extract_json(response_text)

            # Intentar parsear JSON
            try:
                questions_data = json.loads(json_text)
            except json.decoder.JSONDecodeError:
                raise ValueError(f"Claude no devolvió JSON válido: {json_text[:200]}")

            if not isinstance(questions_data, list):
                raise ValueError("Claude devolvió formato incorrecto (debe ser una lista)")

            # Convertir a objetos Question
            questions = []
            for i, q in enumerate(questions_data):
                try:
                    questions.append(Question(**q))
                except Exception as e:
                    raise ValueError(f"Error en pregunta {i+1}: {e}")

            return questions
        except Exception as e:
            print(f"Error generando preguntas: {e}")
            raise

question_service = QuestionService()