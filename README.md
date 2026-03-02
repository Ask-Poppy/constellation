# Constellation

Structured K-12 curriculum data for education systems worldwide. Machine-readable JSON files organized by country, subject, and grade band — designed for AI tool integration.

## Structure

```
countries/
  norway/
    metadata.json              # Education system overview
    subjects/
      mathematics.json         # Competence goals by grade band
      norwegian.json
      english.json
      ...
  sweden/                      # (planned)
  finland/                     # (planned)
  denmark/                     # (planned)
```

## Schema

Each subject file follows a common format:

```json
{
  "country": "norway",
  "source": {
    "api": "https://data.udir.no/kl06/v201906/",
    "curriculum": "LK20",
    "license": "NLOD"
  },
  "subject": {
    "code": "MAT01-05",
    "name": { "local": "Matematikk", "en": "Mathematics" },
    "gradeBands": [
      {
        "grades": [1, 2],
        "label": { "local": "Etter 2. trinn", "en": "After Year 2" },
        "competenceGoals": [
          {
            "code": "KM1234",
            "text": { "local": "...", "en": "..." },
            "coreElements": ["Exploration and problem solving"],
            "verbs": ["explore", "use"]
          }
        ]
      }
    ]
  }
}
```

## Usage

### Raw URL access

Fetch any subject directly:

```
https://raw.githubusercontent.com/Ask-Poppy/constellation/main/countries/norway/subjects/mathematics.json
```

### AI tool integration

Query by country, grade, and subject — the AI fetches only the relevant file and filters by grade band:

```typescript
const goals = await getCompetenceGoals("norway", 5, "mathematics");
// Returns goals from the grade band containing grade 5 (grades 3-4 or 4-7 depending on country)
```

## Data Sources

| Country | Source | API | Status |
|---------|--------|-----|--------|
| Norway | Utdanningsdirektoratet (UDIR) | `data.udir.no` | Available |
| Sweden | Skolverket | `api.skolverket.se` | Planned |
| Finland | Opetushallitus (OPH) | `eperusteet.opintopolku.fi` | Planned |
| Denmark | Børne- og Undervisningsministeriet | PDFs (no API) | Planned |

## Sync

Fetch/update curriculum data from government APIs:

```bash
python scripts/sync_norway.py
```

## Contributing

To add a new country:

1. Create `countries/{country}/metadata.json`
2. Add subject files following the schema above
3. If the country has a public API, add a sync script in `scripts/`
4. Submit a PR

## License

Data: Licensed per source (see each country's `metadata.json`).
Code: MIT.
