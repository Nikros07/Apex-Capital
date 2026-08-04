# Investoren-Deck neu erzeugen

Das Deck unter `docs/Apex-Capital-Investor-Pitch.pptx` wird aus `deck.js` erzeugt —
Inhalt und Layout also im Code ändern, nicht in PowerPoint, sonst geht die
Änderung beim nächsten Lauf verloren.

```bash
cd docs/pitch
npm install pptxgenjs          # einmalig
node deck.js ../Apex-Capital-Investor-Pitch.pptx
```

Aufbau: 18 Folien, deutsch, dunkles Terminal-Design mit der Farbpalette der
Dashboards (`static/index.html`). Zahlen und Regeln stammen direkt aus dem Code —
wenn sich `MAX_POSITIONS`, die Risikoregeln in `agents/risk.py` oder der
Zeitplan in `core/scheduler.py` ändern, müssen die Folien 3, 9 und 11 nachgezogen
werden.

Folie 15 ("Offene Punkte") und Folie 16 ("Roadmap") sind die Kurzfassung von
[`../VERBESSERUNGEN.md`](../VERBESSERUNGEN.md).
