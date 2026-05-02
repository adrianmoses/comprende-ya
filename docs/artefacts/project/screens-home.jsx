// Home + Library screens
const { useState: hUseState } = React;

function Home({ go }) {
  return (
    <div className="page">
      <h1 className="page-h">Buenos días, Ana.</h1>
      <p className="page-sub">
        Sigues con <em>Lo que los mercados de barrio nos enseñan</em>. Te quedan ocho minutos
        y dos preguntas en este episodio.
      </p>

      <div className="kpis">
        <div className="kpi">
          <div className="kpi-label">Esta semana</div>
          <div className="kpi-val">42<small>min</small></div>
        </div>
        <div className="kpi">
          <div className="kpi-label">Frases guardadas</div>
          <div className="kpi-val">{window.CHUNKS.length}</div>
        </div>
        <div className="kpi">
          <div className="kpi-label">Racha</div>
          <div className="kpi-val">6<small>días</small></div>
        </div>
        <div className="kpi">
          <div className="kpi-label">Comprensión</div>
          <div className="kpi-val">84<small>%</small></div>
        </div>
      </div>

      <div className="section-title">
        Continúa escuchando
        <span className="meta">Última escucha · hace 2 horas</span>
      </div>
      <div className="lib-grid" style={{ marginBottom: 40 }}>
        {window.LIBRARY.filter(e => e.progress > 0 && e.progress < 1).slice(0, 3).map(ep => (
          <button key={ep.id} className="card" onClick={() => go({ view: 'listen', id: ep.id })} style={{appearance:'none', textAlign:'left', padding: 0, font:'inherit', color:'inherit'}}>
            <Thumb color={ep.color} label={`▶ ${ep.channel}`} pattern={ep.pattern} duration={ep.duration} progress={ep.progress} />
            <div className="card-body">
              <div className="card-title">{ep.title}</div>
              <div className="card-meta">
                <span className="tag level">{ep.level}</span>
                <span>{ep.channel}</span>
              </div>
            </div>
          </button>
        ))}
      </div>

      <div className="section-title">
        Tu biblioteca
        <span className="meta">{window.LIBRARY.length} episodios</span>
      </div>
      <div className="lib-grid">
        {window.LIBRARY.map(ep => (
          <button key={ep.id} className="card" onClick={() => go({ view: 'listen', id: ep.id })} style={{appearance:'none', textAlign:'left', padding: 0, font:'inherit', color:'inherit'}}>
            <Thumb color={ep.color} label={`▶ ${ep.channel}`} pattern={ep.pattern} duration={ep.duration} progress={ep.progress} />
            <div className="card-body">
              <div className="card-title">{ep.title}</div>
              <div className="card-meta">
                <span className="tag level">{ep.level}</span>
                <span>{ep.channel}</span>
              </div>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
window.Home = Home;

function ChunksPage({ go }) {
  const [filter, setFilter] = hUseState('all');
  const [recordingId, setRecordingId] = hUseState(null);
  const [promptIdx, setPromptIdx] = hUseState({});

  const chunks = window.CHUNKS.filter(c => {
    if (filter === 'all') return true;
    if (filter === 'low') return c.mastery < 0.4;
    if (filter === 'recent') return c.saved.toLowerCase().includes('today') || c.saved.toLowerCase().includes('day');
    return true;
  });

  const cyclePrompt = (id, total) => {
    setPromptIdx(prev => ({ ...prev, [id]: ((prev[id] ?? 0) + 1) % total }));
  };

  const toggleRec = (id) => {
    setRecordingId(prev => prev === id ? null : id);
    if (recordingId !== id) {
      setTimeout(() => setRecordingId(curr => curr === id ? null : curr), 3500);
    }
  };

  return (
    <div className="page">
      <h1 className="page-h">Tu biblioteca de frases</h1>
      <p className="page-sub">
        Cada frase venía de algo que escuchaste. Practícala en voz alta hasta que salga sin
        pensar — los prompts cambian para que no memorices la respuesta.
      </p>

      <div className="filter-row">
        <button className={`chip ${filter === 'all' ? 'is-on' : ''}`} onClick={() => setFilter('all')}>
          Todas · {window.CHUNKS.length}
        </button>
        <button className={`chip ${filter === 'low' ? 'is-on' : ''}`} onClick={() => setFilter('low')}>
          Necesitan práctica
        </button>
        <button className={`chip ${filter === 'recent' ? 'is-on' : ''}`} onClick={() => setFilter('recent')}>
          Añadidas esta semana
        </button>
        <div style={{ flex: 1 }} />
        <button className="btn sm">Empezar sesión de práctica</button>
      </div>

      <div className="chunks-grid">
        {chunks.map(c => {
          const pIdx = promptIdx[c.id] ?? 0;
          const masteryDots = Math.round(c.mastery * 5);
          const isRec = recordingId === c.id;
          return (
            <div key={c.id} className="chunk">
              <div className="chunk-h">
                <div>
                  <h3 className="chunk-phrase">{c.phrase}</h3>
                  <div className="chunk-gloss">{c.gloss}</div>
                </div>
                <div className="mastery">
                  <div className="mastery-dots">
                    {[0, 1, 2, 3, 4].map(i => (
                      <span key={i} className={`mastery-dot ${i < masteryDots ? 'on' : ''}`} />
                    ))}
                  </div>
                </div>
              </div>
              <div className="chunk-source">
                <span style={{opacity: 0.6}}>de</span> {c.source} · {c.saved}
              </div>
              <div className="chunk-prompt">
                {c.prompts[pIdx]}
              </div>
              <div className="chunk-actions">
                <button className={`rec-btn ${isRec ? 'is-recording' : ''}`} onClick={() => toggleRec(c.id)}>
                  <span className="rec-dot" />
                  {isRec ? 'Grabando…' : 'Grabar respuesta'}
                </button>
                <button className="cycle-btn" onClick={() => cyclePrompt(c.id, c.prompts.length)}>
                  Otro prompt →
                </button>
                <div style={{flex: 1}} />
                <span style={{ fontSize: 11, color: 'var(--ink-3)', fontFamily: 'var(--font-mono)' }}>
                  {pIdx + 1}/{c.prompts.length}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
window.ChunksPage = ChunksPage;
