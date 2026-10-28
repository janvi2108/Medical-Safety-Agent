import assert from 'node:assert/strict'
import { after, before, test } from 'node:test'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer } from 'vite'

let vite
let App
let ClinicalNoteInput
let InteractionCard
let MedicationTable
let PatientSummary
let Disclaimer
let LoadingState
let ErrorMessage
let analyzeClinicalNote
let getApiBaseUrl
let previousApiBase
let previousFetch

before(async () => {
  previousApiBase = process.env.VITE_API_BASE_URL
  previousFetch = globalThis.fetch
  process.env.VITE_API_BASE_URL = 'http://127.0.0.1:8001'
  vite = await createServer({
    configFile: './vite.config.js',
    server: { middlewareMode: true },
    appType: 'custom',
  })
  App = (await vite.ssrLoadModule('/src/App.jsx')).default
  ClinicalNoteInput = (await vite.ssrLoadModule('/src/components/ClinicalNoteInput.jsx')).default
  InteractionCard = (await vite.ssrLoadModule('/src/components/InteractionCard.jsx')).default
  MedicationTable = (await vite.ssrLoadModule('/src/components/MedicationTable.jsx')).default
  PatientSummary = (await vite.ssrLoadModule('/src/components/PatientSummary.jsx')).default
  Disclaimer = (await vite.ssrLoadModule('/src/components/Disclaimer.jsx')).default
  LoadingState = (await vite.ssrLoadModule('/src/components/LoadingState.jsx')).default
  ErrorMessage = (await vite.ssrLoadModule('/src/components/ErrorMessage.jsx')).default
  const apiModule = await vite.ssrLoadModule('/src/services/api.js')
  analyzeClinicalNote = apiModule.analyzeClinicalNote
  getApiBaseUrl = apiModule.getApiBaseUrl
})

after(async () => {
  if (vite) await vite.close()
  if (previousApiBase === undefined) delete process.env.VITE_API_BASE_URL
  else process.env.VITE_API_BASE_URL = previousApiBase
  globalThis.fetch = previousFetch
})

const render = (element) => renderToStaticMarkup(element)

function interaction(sourceRisk) {
  const normalized = sourceRisk.toLowerCase()
  return {
    drug_a: 'Drug A',
    drug_b: 'Drug B',
    source_risk: sourceRisk,
    normalized_risk: normalized,
    mechanism: null,
    management: null,
    alternative_medications: null,
    source: 'DDInter 2.0',
  }
}

test('initial page includes the controlled note form and examples without fabricated results', () => {
  const markup = render(React.createElement(App))
  assert.match(markup, /Clinical note/)
  assert.match(markup, /Analyze medications/)
  assert.match(markup, /Warfarin \+ aspirin/)
  assert.doesNotMatch(markup, /Extracted medications|Interaction review/)
})

test('note form exposes validation, example labels, and loading-disabled state', () => {
  const validation = render(React.createElement(ClinicalNoteInput, {
    value: '', onChange() {}, onSubmit() {}, disabled: false,
    validationError: 'Enter a synthetic clinical note before analyzing.',
  }))
  assert.match(validation, /aria-invalid="true"/)
  assert.match(validation, /Enter a synthetic clinical note/)
  assert.match(validation, /Metformin \+ lisinopril/)

  const busy = render(React.createElement(ClinicalNoteInput, {
    value: 'synthetic note', onChange() {}, onSubmit() {}, disabled: true,
  }))
  assert.match(busy, /Analyzing/)
  assert.match(busy, /disabled=""/)
})

test('classification and lookup states remain distinct in the UI', () => {
  for (const level of ['Major', 'Moderate', 'Minor']) {
    const markup = render(React.createElement(InteractionCard, {
      interactions: { pairs_checked: 1, interactions_found: [interaction(level)], unmatched_drugs: [] },
    }))
    assert.ok(markup.includes(`DDInter classification: ${level}`))
    assert.ok(markup.includes('not personalized clinical risk assessments'))
  }

  const unknown = render(React.createElement(InteractionCard, {
    interactions: { pairs_checked: 1, interactions_found: [interaction('Unknown')], unmatched_drugs: [] },
  }))
  assert.match(unknown, /DDInter record found/)
  assert.match(unknown, /severity unknown/)

  const noRecord = render(React.createElement(InteractionCard, {
    interactions: { pairs_checked: 1, interactions_found: [], unmatched_drugs: [] },
  }))
  assert.match(noRecord, /No matching record found/)
  assert.match(noRecord, /does not establish that a combination is safe/)
  assert.doesNotMatch(noRecord, /\bSafe\b/)

  const unmatched = render(React.createElement(InteractionCard, {
    interactions: { pairs_checked: 0, interactions_found: [], unmatched_drugs: [{ drug_name: 'Unmatched drug' }] },
  }))
  assert.match(unmatched, /Some medications were not matched/)
})

test('medication missing values and patient disclaimer are explicit', () => {
  const medications = render(React.createElement(MedicationTable, {
    medications: [{ name: 'Warfarin', dose: null, frequency: 'daily', route: null }],
  }))
  assert.match(medications, /Warfarin/)
  assert.equal((medications.match(/Not stated/g) || []).length, 2)

  const patient = render(React.createElement(PatientSummary, {
    summary: {
      explanation: 'DDInter classifications are not personalized clinical conclusions.',
      what_to_know: ['DDInter classification: Moderate.'],
      next_step: 'Review with a qualified healthcare professional.',
    },
  }))
  assert.match(patient, /DDInter classification: Moderate/)
  assert.match(patient, /qualified healthcare professional/)
  assert.match(render(React.createElement(Disclaimer)), /Do not start, stop, or change medication/)
})

test('loading and API errors have accessible messages', () => {
  assert.match(render(React.createElement(LoadingState)), /role="status"/)
  assert.match(render(React.createElement(ErrorMessage, { message: 'Backend unavailable.' })), /role="alert"/)
  assert.match(render(React.createElement(ErrorMessage, { message: 'Backend unavailable.' })), /Backend unavailable/)
})

test('API client sends the configured local request and validates a successful response', async () => {
  let request
  globalThis.fetch = async (url, options) => {
    request = { url, options }
    return {
      ok: true,
      json: async () => ({
        medications: [],
        interactions: { pairs_checked: 0, interactions_found: [], unmatched_drugs: [] },
        safety: { safety_level: 'none', show_critical_banner: false, banner_message: null },
        patient_summary: null,
        warnings: [],
      }),
    }
  }

  const result = await analyzeClinicalNote('Synthetic sample note.')
  assert.equal(request.url, 'http://127.0.0.1:8001/analyze')
  assert.equal(request.options.method, 'POST')
  assert.equal(JSON.parse(request.options.body).clinical_note, 'Synthetic sample note.')
  assert.deepEqual(result.warnings, [])
})

test('API base uses the configured Vite URL, trims its trailing slash, and falls back only in development', () => {
  assert.equal(getApiBaseUrl({ VITE_API_BASE_URL: 'https://api.example.test///', DEV: false }), 'https://api.example.test')
  assert.equal(getApiBaseUrl({ VITE_API_BASE_URL: undefined, DEV: true }), 'http://127.0.0.1:8001')
  assert.equal(getApiBaseUrl({ VITE_API_BASE_URL: undefined, DEV: false }), '')
})

test('API client keeps database failures distinct and rejects malformed success data', async () => {
  globalThis.fetch = async () => ({
    ok: false,
    status: 503,
    json: async () => ({ detail: 'Interaction database is unavailable. No interaction check was completed.' }),
  })
  await assert.rejects(
    () => analyzeClinicalNote('Synthetic note.'),
    /Interaction lookup could not be completed/,
  )

  globalThis.fetch = async () => ({ ok: true, json: async () => ({ medications: [] }) })
  await assert.rejects(
    () => analyzeClinicalNote('Synthetic note.'),
    /incomplete analysis response/,
  )
})
