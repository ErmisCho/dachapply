import {afterEach,describe,expect,it,vi} from 'vitest'
import {renderToStaticMarkup} from 'react-dom/server'
import {MemoryRouter} from 'react-router-dom'
import {MailboxReview} from './App'

function render(canUseMailbox:boolean){
  vi.stubGlobal('localStorage',{
    getItem:(key:string)=>key==='dachapply_user'?JSON.stringify({can_use_mailbox:canUseMailbox}):null,
    removeItem:vi.fn(),
  })
  return renderToStaticMarkup(<MemoryRouter><MailboxReview/></MemoryRouter>)
}

afterEach(()=>vi.unstubAllGlobals())

describe('manual mailbox run',()=>{
  it('shows the owner control before credentials/status load, including on the deployed queue path',()=>{
    expect(render(true)).toContain('Run check now')
  })

  it('does not expose the mailbox trigger to another user',()=>{
    expect(render(false)).not.toContain('Run check now')
  })
})
