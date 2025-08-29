import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import React from 'react'
import { Proposals } from '../main.jsx'

function mockFetch(routes) {
  const fn = vi.fn(async (url, opts) => {
    const path = String(url).replace(/^[^/]*\/api/, '')
    const key = `${opts?.method || 'GET'} ${path}`
    const handler = routes[key]
    if (!handler) return new Response(JSON.stringify({}), { status: 404 })
    const body = opts?.body instanceof FormData ? opts.body : (opts?.body ? JSON.parse(opts.body) : null)
    const res = await handler({ path, body, opts })
    return new Response(JSON.stringify(res.body || {}), { status: res.status || 200, headers: { 'Content-Type': 'application/json' } })
  })
  global.fetch = fn
  return fn
}

describe('Authoring OCR upload', () => {
  it('shows OCR preview after uploading a file and sends file_refs on write', async () => {
    const token = 't'
    const proposal = { id: 1, content: { meta: { title: 'T' }, sections: {} }, schema_version: 'v1', state: 'draft' }
    const serverState = { proposal: JSON.parse(JSON.stringify(proposal)) }
    const routes = {
      'GET /proposals/': async () => ({ body: [serverState.proposal] }),
      'GET /usage': async () => ({ body: { tier: 'pro', status: 'active' } }),
      'POST /ai/plan': async () => ({ body: { schema_version: 'v1', sections: [ { id: 'summary', title: 'Executive Summary', inputs: [] } ] } }),
      'POST /ai/write': async ({ body }) => {
        // Expect file_refs to be present and include the uploaded file
        if (!body || !Array.isArray(body.file_refs) || body.file_refs.length !== 1) {
          return { status: 400, body: { error: 'missing_file_refs' } }
        }
        const f = body.file_refs[0]
        expect(f.url).toContain('/media/uploads/fake.pdf')
        expect(f.ocr_text).toContain('This is extracted text')
        return { body: { draft_text: 'Draft S' } }
      },
      'PATCH /proposals/1/': async ({ body }) => { serverState.proposal = { ...(serverState.proposal || {}), ...body, id: 1 }; return { body: serverState.proposal, status: 200 } },
      'POST /files': async () => ({ body: { id: 10, url: '/media/uploads/fake.pdf', content_type: 'application/pdf', size: 1234, ocr_text: 'This is extracted text' } }),
    }
    mockFetch(routes)

    render(<Proposals token={token} />)

    await screen.findByText(/My Proposals/i)
    fireEvent.click(await screen.findByRole('button', { name: /Open Author/i }))
    fireEvent.click(await screen.findByRole('button', { name: /^Start$/ }))
    await screen.findByText(/Section 1 \/ 1/i)

    const fileInput = await screen.findByLabelText(/Attach files/i)
    const file = new File([new Uint8Array([0x25,0x50,0x44,0x46])], 'sample.pdf', { type: 'application/pdf' })
    await waitFor(() => {
      fireEvent.change(fileInput, { target: { files: [file] } })
    })

  // Expect OCR preview area to show the returned text
    await screen.findByText(/OCR preview/i)
    const ta = await screen.findByDisplayValue(/This is extracted text/i)
    expect(ta).toBeTruthy()

  // Click Write and ensure the request includes file_refs
  const writeBtn = await screen.findByRole('button', { name: /^Write$/ })
  fireEvent.click(writeBtn)
  // Draft text renders inside a <pre>, so assert by text content
  await screen.findByText(/Draft S/)
  })
})
