import {describe,expect,it,vi} from 'vitest'
import {renderToStaticMarkup} from 'react-dom/server'
import {FollowUpDraftBlock,saveFollowUpDraft,type FollowUpDraft} from './App'

const draft:FollowUpDraft={to:['hr@acme.test'],subject:'Re: Application: Engineer',body_text:'Dear Jane,\nfollowing up.',reply_to_message_id:7,provider:'openai',model:'gpt-5',reason:''}

describe('feedback-deadline follow-up draft (TASK-288)',()=>{
  it('saves through the existing reply compose path, threaded onto the job mail, with the edited text',async()=>{
    const request=vi.fn().mockResolvedValue({id:7})
    await saveFollowUpDraft(draft,'hr@acme.test, boss@acme.test','Edited body',request)
    expect(request).toHaveBeenCalledWith('/mailbox-messages/7/reply/',{method:'POST',body:{body_text:'Edited body',to:['hr@acme.test','boss@acme.test'],cc:[]}})
  })

  it('shows recipient, subject and editable body with copy and save actions',()=>{
    const html=renderToStaticMarkup(<FollowUpDraftBlock jobId={42} initialDraft={draft}/>)
    expect(html).toContain('value="hr@acme.test"')
    expect(html).toContain('Re: Application: Engineer')
    expect(html).toContain('Dear Jane,\nfollowing up.')
    expect(html).toContain('Copy')
    expect(html).toContain('Save to Gmail Drafts')
    expect(html).toContain('Regenerate')
  })

  it('says why no draft was generated and still offers the recipient',()=>{
    const html=renderToStaticMarkup(<FollowUpDraftBlock jobId={42} initialDraft={{...draft,body_text:'',provider:'',model:'',reason:'the codex CLI is not installed on this machine'}}/>)
    expect(html).toContain('No draft generated: the codex CLI is not installed on this machine')
    expect(html).toContain('value="hr@acme.test"')
  })
})
