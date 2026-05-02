// Active Listening view — video, scrubber, transcript with tappable words,
// post-segment MCQ, and right-rail Phrase Autopsy.

const { useState: lUseState, useEffect: lUseEffect, useRef: lUseRef, useMemo: lUseMemo } = React;

function Listen({ episodeId, go, tweaks, savePhrase, savedPhrases, openAutopsy, autopsyTarget, closeAutopsy }) {
  const ep = window.LIBRARY.find(e => e.id === episodeId) || window.LIBRARY[0];
  const totalSec = 14 * 60 + 32; // matches "14:32"
  const transcriptEnd = window.TRANSCRIPT[window.TRANSCRIPT.length - 1].end;

  const [time, setTime] = lUseState(46); // start mid-segment for instant context
  const [playing, setPlaying] = lUseState(false);
  const [speed, setSpeed] = lUseState(1);
  const [answeredQuestions, setAnsweredQuestions] = lUseState({}); // { segId: 'a' }
  const [pendingQuestionFor, setPendingQuestionFor] = lUseState(null);
  const [showLiteral, setShowLiteral] = lUseState(false);

  // Tick the clock when playing — synthetic, since there's no real video
  lUseEffect(() => {
    if (!playing) return;
    const id = setInterval(() => {
      setTime(t => {
        const next = t + 0.25 * speed;
        if (next >= transcriptEnd) {
          setPlaying(false);
          return transcriptEnd;
        }
        return next;
      });
    }, 250);
    return () => clearInterval(id);
  }, [playing, speed, transcriptEnd]);

  // When playback crosses a segment that has a question, pause and surface it
  lUseEffect(() => {
    for (const q of window.QUESTIONS) {
      const seg = window.TRANSCRIPT.find(s => s.id === q.afterSegment);
      if (!seg) continue;
      if (time >= seg.end && !answeredQuestions[q.afterSegment] && pendingQuestionFor !== q.afterSegment) {
        setPendingQuestionFor(q.afterSegment);
        setPlaying(false);
        // Snap time exactly to seg.end so we don't drift past
        setTime(seg.end);
        break;
      }
    }
  }, [time, answeredQuestions, pendingQuestionFor]);

  const currentSegment = window.TRANSCRIPT.find(s => time >= s.start && time < s.end) || window.TRANSCRIPT[0];

  // Active aside content: question > autopsy > saved confirmation > nothing
  const pendingQ = pendingQuestionFor ? window.QUESTIONS.find(q => q.afterSegment === pendingQuestionFor) : null;

  const onScrub = (e) => {
    const r = e.currentTarget.getBoundingClientRect();
    const pct = Math.max(0, Math.min(1, (e.clientX - r.left) / r.width));
    setTime(pct * transcriptEnd);
  };

  const handleAnswer = (qSegId, choiceId) => {
    setAnsweredQuestions(prev => ({ ...prev, [qSegId]: choiceId }));
  };

  const continueAfterQuestion = () => {
    setPendingQuestionFor(null);
    setPlaying(true);
  };

  const onTapWord = (segId, range, phrase) => {
    if (range) {
      openAutopsy(phrase, range, segId);
    }
  };

  return (
    <div className="listen">
      <div>
        {/* Video frame */}
        <div className="video-wrap">
          <div className="video-canvas" style={{
            background: `linear-gradient(135deg, ${ep.color}, oklch(0.55 0.05 35))`,
          }} />
          <div className="video-stripes stripes-thick" />
          <button className={`play-btn ${playing ? 'is-playing' : ''}`} onClick={() => setPlaying(p => !p)}>
            {playing ? <IconPause className="i-xl" style={{color:'var(--ink)'}} /> : <IconPlay className="i-xl" style={{color:'var(--ink)', marginLeft: 3}} />}
          </button>
          <div className="video-overlay">
            <div>
              <div className="video-title">{ep.title}</div>
              <div className="video-channel">{ep.channel} · {ep.level}</div>
            </div>
          </div>
        </div>

        {/* Scrubber */}
        <div className="scrubber">
          <div className="scrubber-time">{fmtTime(time)}</div>
          <div className="scrub-bar" onClick={onScrub}>
            <div className="scrub-fill" style={{ width: `${(time / totalSec) * 100}%` }} />
            {window.QUESTIONS.map(q => {
              const seg = window.TRANSCRIPT.find(s => s.id === q.afterSegment);
              if (!seg) return null;
              return <div key={q.afterSegment} className="scrub-mark" style={{ left: `${(seg.end / totalSec) * 100}%` }} />;
            })}
            <div className="scrub-thumb" style={{ left: `${(time / totalSec) * 100}%` }} />
          </div>
          <div className="scrubber-time" style={{ textAlign: 'right' }}>{ep.duration}</div>
        </div>

        <div className="transport">
          <button className="btn ghost sm" onClick={() => setTime(t => Math.max(0, t - 5))}>
            <IconBack className="i" /> 5s
          </button>
          <button className="btn ghost sm" onClick={() => setTime(t => Math.min(transcriptEnd, t + 5))}>
            5s <IconFwd className="i" />
          </button>
          <button
            className="speed"
            onClick={() => setSpeed(s => s === 1 ? 0.85 : s === 0.85 ? 0.7 : s === 0.7 ? 1.25 : 1)}
            style={{cursor:'default'}}
          >
            {speed}×
          </button>
          <div style={{ flex: 1 }} />
          <span style={{ fontSize: 11.5, color: 'var(--ink-3)', display: 'flex', alignItems: 'center', gap: 6 }}>
            <span className="scrub-mark" style={{ position: 'relative', display: 'inline-block', width: 2, height: 12, top: 'auto' }} />
            Pregunta de comprensión
          </span>
        </div>

        {/* Transcript */}
        <div className="transcript">
          <div className="transcript-h">
            <h3>Transcripción</h3>
            <div className="toggle-row">
              <button className={!showLiteral ? 'is-active' : ''} onClick={() => setShowLiteral(false)}>Español</button>
              <button className={showLiteral ? 'is-active' : ''} onClick={() => setShowLiteral(true)}>+ Inglés</button>
            </div>
          </div>

          {window.TRANSCRIPT.map(seg => {
            const isCurrent = currentSegment.id === seg.id;
            // Resolve autopsy tokenRange dynamically from `words` so it stays correct even with punctuation tokens interleaved.
            let autopsyRange = null;
            if (seg.autopsy?.words) {
              const words = seg.autopsy.words;
              const norm = (s) => s.toLowerCase().replace(/[¿¡?!.,]/g, '');
              for (let i = 0; i <= seg.tokens.length - 1; i++) {
                let j = 0, k = i;
                while (k < seg.tokens.length && j < words.length) {
                  const tok = seg.tokens[k];
                  if (tok.p) { k++; continue; }
                  if (norm(tok.t) === norm(words[j])) { j++; k++; }
                  else break;
                }
                if (j === words.length) { autopsyRange = [i, k]; break; }
              }
            }
            return (
              <div key={seg.id} className={`segment ${isCurrent ? 'is-current' : ''}`}>
                <div className="seg-speaker">
                  <span>{seg.speaker}</span>
                  <span className="ts">{fmtTime(seg.start)}</span>
                </div>
                <div className="seg-text">
                  {seg.tokens.map((tok, i) => {
                    if (tok.p) return <span key={i} className="punct">{tok.p}{' '}</span>;
                    const inAutopsy = autopsyRange && i >= autopsyRange[0] && i < autopsyRange[1];
                    const isSaved = inAutopsy && savedPhrases.includes(seg.autopsy.phrase);
                    const isActiveAutopsy = inAutopsy && autopsyTarget?.segId === seg.id;
                    const tappable = inAutopsy;
                    return (
                      <span
                        key={i}
                        className={`word ${tappable ? '' : 'plain'} ${isSaved ? 'is-saved' : ''} ${isActiveAutopsy ? 'is-active' : ''}`}
                        onClick={() => tappable && onTapWord(seg.id, autopsyRange, seg.autopsy.phrase)}
                        style={{cursor: tappable ? 'default' : 'text'}}
                      >
                        {tok.t}{' '}
                      </span>
                    );
                  })}
                  {showLiteral && seg.id === 's2' && (
                    <div style={{ marginTop: 8, fontSize: 13, color: 'var(--ink-3)', fontStyle: 'italic' }}>
                      People greet each other by name, ask after each other's kids, and along the way, buy tomatoes.
                    </div>
                  )}
                  {showLiteral && seg.id === 's4' && (
                    <div style={{ marginTop: 8, fontSize: 13, color: 'var(--ink-3)', fontStyle: 'italic' }}>
                      I know her, you know? And if one day she doesn't show up, well, I worry. You don't get that at the supermarket.
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* ── Right rail ───────────────────────────────── */}
      <aside className="aside">
        {pendingQ && (
          <QuestionPanel
            q={pendingQ}
            answered={answeredQuestions[pendingQ.afterSegment]}
            onAnswer={(c) => handleAnswer(pendingQ.afterSegment, c)}
            onContinue={continueAfterQuestion}
          />
        )}
        {!pendingQ && autopsyTarget && (
          <AutopsyPanel
            target={autopsyTarget}
            onClose={closeAutopsy}
            onSave={() => savePhrase(autopsyTarget.phrase)}
            isSaved={savedPhrases.includes(autopsyTarget.phrase)}
          />
        )}
        {!pendingQ && !autopsyTarget && (
          <div className="aside-empty">
            <strong>Toca una frase subrayada</strong>
            <div style={{marginTop: 6}}>para ver por qué suena natural — o sigue escuchando hasta la próxima pregunta.</div>
          </div>
        )}

        {/* Always-visible hint card showing question progress */}
        <div className="panel">
          <div className="panel-h">
            <h4>Sesión</h4>
            <span className="panel-tag">{Object.keys(answeredQuestions).length}/{window.QUESTIONS.length} preguntas</span>
          </div>
          <div className="panel-body" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {window.QUESTIONS.map((q, i) => {
              const ans = answeredQuestions[q.afterSegment];
              const isCorrect = ans === q.correct;
              return (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 13 }}>
                  <div style={{
                    width: 18, height: 18, borderRadius: '50%',
                    background: ans ? (isCorrect ? 'var(--good)' : 'var(--bad)') : 'var(--paper-3)',
                    display: 'grid', placeItems: 'center', flexShrink: 0,
                    color: 'white', fontSize: 11, fontWeight: 600,
                  }}>{ans ? (isCorrect ? '✓' : '×') : i + 1}</div>
                  <div style={{ flex: 1, color: ans ? 'var(--ink-2)' : 'var(--ink-3)' }}>
                    {ans ? 'Respondida' : `Aparece a las ${fmtTime(window.TRANSCRIPT.find(s => s.id === q.afterSegment).end)}`}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </aside>
    </div>
  );
}

function QuestionPanel({ q, answered, onAnswer, onContinue }) {
  const isCorrect = answered === q.correct;
  return (
    <div className="panel">
      <div className="panel-h">
        <h4><IconSpark className="i" style={{color:'var(--accent)'}} /> Pregunta de comprensión</h4>
        <span className="panel-tag">después del segmento</span>
      </div>
      <div className="panel-body">
        <div className="q-meta">¿Lo captaste?</div>
        <p className="q-prompt">{q.prompt}</p>
        <div className="choices">
          {q.choices.map(c => {
            let cls = 'choice';
            if (answered) {
              if (c.id === q.correct) cls += ' is-correct';
              else if (c.id === answered) cls += ' is-wrong';
              else cls += ' is-disabled';
            }
            return (
              <button key={c.id} className={cls} onClick={() => !answered && onAnswer(c.id)}>
                <span className="key">{c.id.toUpperCase()}</span>
                <span>{c.text}</span>
              </button>
            );
          })}
        </div>
        {answered && (
          <Fragment>
            <div className="q-explain">
              {isCorrect ? '✓ Exacto. ' : 'No del todo. '}
              {q.explain}
            </div>
            <div className="q-foot">
              <button className="btn ghost sm">Volver a escuchar este segmento</button>
              <button className="btn primary" onClick={onContinue}>
                Seguir <IconArrow className="i" />
              </button>
            </div>
          </Fragment>
        )}
      </div>
    </div>
  );
}

function AutopsyPanel({ target, onClose, onSave, isSaved }) {
  const data = window.AUTOPSY[target.phrase];
  const [openLayers, setOpenLayers] = lUseState({ natural: true, grammar: true, register: true });
  if (!data) return null;
  const toggle = (k) => setOpenLayers(s => ({ ...s, [k]: !s[k] }));
  return (
    <div className="panel">
      <div className="panel-h">
        <h4><IconAutopsy className="i" /> Phrase Autopsy</h4>
        <button className="btn ghost sm" onClick={onClose} style={{padding: 4}}>
          <IconClose className="i" />
        </button>
      </div>
      <div className="panel-body" style={{ paddingBottom: 14 }}>
        <h2 className="autopsy-phrase">«{target.phrase}»</h2>
        <div className="autopsy-natural">{data.natural}</div>
        <div className="autopsy-register">{data.register}</div>
      </div>

      <div className={`layer ${openLayers.natural ? 'is-open' : ''}`}>
        <div className="layer-h" onClick={() => toggle('natural')}>
          <span className="layer-num">1</span>
          <span className="layer-title">Significado natural</span>
          <IconChev className="layer-chev i" />
        </div>
        {openLayers.natural && (
          <div className="layer-body">
            <div style={{ fontFamily: 'var(--font-ed)', fontSize: 18, color: 'var(--ink)', marginBottom: 10, lineHeight: 1.3 }}>
              "{data.natural}"
            </div>
            <div style={{ fontSize: 12, color: 'var(--ink-3)', fontStyle: 'italic' }}>
              palabra por palabra: <span style={{ fontFamily: 'var(--font-mono)' }}>{data.literal}</span>
            </div>
          </div>
        )}
      </div>

      <div className={`layer ${openLayers.grammar ? 'is-open' : ''}`}>
        <div className="layer-h" onClick={() => toggle('grammar')}>
          <span className="layer-num">2</span>
          <span className="layer-title">Gramática</span>
          <IconChev className="layer-chev i" />
        </div>
        {openLayers.grammar && (
          <div className="layer-body">
            {data.grammar.map((g, i) => (
              <div key={i} className="gram-row">
                <div className="gram-tag">{g.tag}</div>
                <div>{g.text}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className={`layer ${openLayers.register ? 'is-open' : ''}`}>
        <div className="layer-h" onClick={() => toggle('register')}>
          <span className="layer-num">3</span>
          <span className="layer-title">Por qué suena natural</span>
          <IconChev className="layer-chev i" />
        </div>
        {openLayers.register && (
          <div className="layer-body">
            {data.natural_notes.map((n, i) => (
              <div key={i} className="nat-row">— {n}</div>
            ))}
          </div>
        )}
      </div>

      <div className="autopsy-foot">
        <button className={isSaved ? 'btn accent' : 'btn primary'} onClick={onSave}>
          {isSaved ? <IconBookmarkFilled className="i" /> : <IconBookmark className="i" />}
          {isSaved ? 'Guardada en biblioteca' : 'Guardar en biblioteca'}
        </button>
        <div style={{ flex: 1 }} />
        <button className="btn ghost sm">Re-escuchar</button>
      </div>
    </div>
  );
}

window.Listen = Listen;
