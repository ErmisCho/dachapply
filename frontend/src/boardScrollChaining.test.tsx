import {describe,expect,it} from 'vitest'
import {splitBoardWheelDelta} from './App'

describe('job board scroll chaining',()=>{
  it('keeps ordinary wheel movement inside the board',()=>{
    expect(splitBoardWheelDelta(400,2000,800,180)).toEqual({board:180,page:0})
    expect(splitBoardWheelDelta(400,2000,800,-180)).toEqual({board:-180,page:0})
  })

  it('hands the unconsumed bottom and top remainder to the page',()=>{
    expect(splitBoardWheelDelta(1150,2000,800,180)).toEqual({board:50,page:130})
    expect(splitBoardWheelDelta(30,2000,800,-180)).toEqual({board:-30,page:-150})
    expect(splitBoardWheelDelta(1200,2000,800,180)).toEqual({board:0,page:180})
    expect(splitBoardWheelDelta(0,2000,800,-180)).toEqual({board:0,page:-180})
  })
})
