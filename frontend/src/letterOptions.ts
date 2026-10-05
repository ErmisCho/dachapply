// TASK-262: a letter may be in a different language from the CV. Same-language letters stay first
// and stay the default; cross-language ones are offered but labelled, and warned about when picked.
export type LetterTemplate={key:string;language:string;label:string}
export type LetterOption={key:string;label:string;recommended:boolean}

export function letterOptions(letters:LetterTemplate[],cvLanguage:string):LetterOption[]{
  const same=letters.filter(x=>x.language===cvLanguage),other=letters.filter(x=>x.language!==cvLanguage)
  return [...same.map(x=>({key:x.key,label:x.label,recommended:true})),...other.map(x=>({key:x.key,label:`${x.label} (not recommended)`,recommended:false}))]
}

export function defaultLetter(letters:LetterTemplate[],cvLanguage:string):string{
  return letters.find(x=>x.language===cvLanguage)?.key||''
}

export function letterMismatchWarning(letters:LetterTemplate[],cvLanguage:string,letterKey:string):string{
  const letter=letterKey?letters.find(x=>x.key===letterKey):undefined
  if(!letter||letter.language===cvLanguage)return ''
  return `The letter (${letter.language.toUpperCase()}) is not in the CV's language (${cvLanguage.toUpperCase()}). Not recommended: most employers expect both in one language.`
}
