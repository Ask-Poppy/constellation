# Constellation

Structured K-12 curriculum data for Nordic education systems. Machine-readable JSON files organized by country, subject, and grade band — designed for AI tool integration.

## Structure

```
countries/
  norway/
    metadata.json
    subjects/
      mathematics.json
      social-studies.json
      ...
  sweden/
    metadata.json
    subjects/
      mathematics.json
      social-studies.json
      ...
  finland/
    metadata.json
    subjects/
      mathematics.json
      social-studies.json
      ...
```

## Schema

Each subject file follows a common format:

```json
{
  "country": "norway",
  "source": {
    "api": "https://data.udir.no/kl06/v201906/laereplaner-lk20/MAT01-05",
    "curriculum": "LK20",
    "license": "NLOD",
    "lastSynced": "2026-03-03T..."
  },
  "subject": {
    "code": "MAT01-05",
    "name": { "local": "Matematikk", "en": "Mathematics" },
    "description": {
      "local": "Matematikk er et sentralt fag...",
      "en": "Mathematics is a fundamental subject..."
    },
    "coreElements": [
      {
        "code": "KE123",
        "name": { "local": "...", "en": "..." },
        "description": { "local": "...", "en": "..." }
      }
    ],
    "interdisciplinaryThemes": [
      {
        "code": "TT1",
        "name": { "local": "Folkehelse og livsmestring", "en": "Health and life skills" },
        "description": { "local": "...", "en": "..." }
      }
    ],
    "basicSkills": [
      {
        "code": "GF1",
        "name": { "local": "Muntlige ferdigheter", "en": "Oral skills" },
        "description": { "local": "...", "en": "..." }
      }
    ],
    "gradeBands": [
      {
        "afterGrade": 4,
        "label": { "local": "Etter 4. trinn", "en": "After Year 4" },
        "competenceGoals": [
          {
            "code": "KM1234",
            "text": { "local": "...", "en": "..." },
            "coreElements": ["Exploration and problem solving"],
            "verbs": ["explore", "use"]
          }
        ],
        "assessment": [
          {
            "type": { "local": "Standpunktvurdering", "en": "Assessment of coursework" },
            "description": { "local": "..." }
          }
        ]
      }
    ]
  }
}
```

### Field Reference

| Field | Description | Countries |
|-------|-------------|-----------|
| `description` | Subject purpose and relevance | Norway, Sweden, Finland |
| `coreElements` | Key knowledge areas within the subject | All |
| `interdisciplinaryThemes` | Cross-subject themes (health, democracy, sustainability) | Norway |
| `basicSkills` | Foundational skills applied in the subject (oral, reading, writing, numeracy, digital) | Norway |
| `gradeBands[].assessment` | Assessment arrangements (coursework, exams) for the grade band | Norway |
| `gradeBands[].knowledgeCriteria` | Graded knowledge requirements (E through A) | Sweden |

### Bilingual Text

All text fields use `{ "local": "...", "en": "..." }` where `local` is the country's language (Norwegian Bokmål, Swedish, or Finnish) and `en` is the English translation.

## Usage

### Raw URL access

Fetch any subject directly:

```
https://raw.githubusercontent.com/Ask-Poppy/constellation/main/countries/norway/subjects/mathematics.json
```

### Query tool

```bash
python scripts/query.py --stats                    # Overview of all countries
python scripts/query.py norway --list              # List subjects
python scripts/query.py norway 5 mathematics       # Goals for grade 5 math
```

## Data Sources

| Country | Source | API | Curriculum | Subjects |
|---------|--------|-----|------------|----------|
| Norway | Utdanningsdirektoratet (UDIR) | `data.udir.no` | LK20 | 13 |
| Sweden | Skolverket | `api.skolverket.se` | Lgr22 | 20 |
| Finland | Opetushallitus (OPH) | `eperusteet.opintopolku.fi` | POPS 2014 | 19 |

## Sync

Fetch/update curriculum data from government APIs:

```bash
python scripts/sync_norway.py              # All Norwegian subjects
python scripts/sync_norway.py SAF01-04     # Single subject by code
python scripts/sync_sweden.py              # All Swedish subjects
python scripts/sync_finland.py             # All Finnish subjects
```

## License

Data: Licensed per source (see each country's `metadata.json`).
Code: MIT.
