// TASK-289: the board banner for a failing mailbox check. react-dom/server like the other panel tests
// (no DOM in this vitest run, TASK-177); the board-load fetch itself is verified in a browser.
import {describe,expect,it} from 'vitest'
import {renderToStaticMarkup} from 'react-dom/server'
import {MailboxHealthBanner} from './App'

describe('mailbox health banner (TASK-289)',()=>{
  it('says what is wrong, what to do and since when',()=>{
    const since='2026-08-31T09:00:00Z'
    const html=renderToStaticMarkup(<MailboxHealthBanner health={{message:'Gmail login expired',action:'Re-authorize Gmail: run manage.py gmail_oauth_setup (see docs/email-setup.md).',since}}/>)
    expect(html).toContain('role="alert"')
    expect(html).toContain('Gmail login expired')
    expect(html).toContain('gmail_oauth_setup')
    expect(html).toContain(new Date(since).toLocaleString())
  })
  it('renders nothing once checks are healthy again',()=>{
    expect(renderToStaticMarkup(<MailboxHealthBanner health={null}/>)).toBe('')
  })
})
