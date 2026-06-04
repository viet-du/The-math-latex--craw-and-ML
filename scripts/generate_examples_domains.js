const fs = require('fs');
const path = require('path');
const p = path.join(__dirname, '..', 'formulas', 'datasheet.json');
const data = JSON.parse(fs.readFileSync(p,'utf8'));
let added = 0;

function addExample(item, ex){
  if(!item.example_problems) item.example_problems = [];
  const exists = item.example_problems.some(e=>JSON.stringify(e.input_values)===JSON.stringify(ex.input_values) && e.output===ex.output);
  if(!exists){ item.example_problems.push(ex); added++; }
}

for(const item of data){
  const tags = (item.tags||[]).map(t=>t.toString().toLowerCase());
  const canon = (item.canonical_form||item.output||'').toString().toLowerCase();
  const instr = (item.instruction||'').toString().toLowerCase();

  // PROBABILITY: conditional, bayes, union/intersection, complement
  if(tags.includes('probability') || /probability|p\(|bayes|conditional|conditional probability/.test(canon+instr)){
    // union/intersection
    const pA = +(Math.random()*0.5+0.1).toFixed(3);
    const pB = +(Math.random()*0.5+0.1).toFixed(3);
    const pInt = +(Math.random()*Math.min(pA,pB)).toFixed(3);
    addExample(item,{input_values:{P_A:pA,P_B:pB,P_A_inter_B:pInt}, output:`P(A\\cup B) = ${+(pA+pB-pInt).toFixed(3)}`});
    // conditional
    const pCond = pInt>0? +(pInt/pB).toFixed(3) : 0;
    addExample(item,{input_values:{P_A_inter_B:pInt,P_B:pB}, output:`P(A|B) = ${pCond}`});
    // Bayes small
    const pH = +(Math.random()*0.6+0.1).toFixed(3);
    const pE_given_H = +(Math.random()*0.9).toFixed(3);
    const pNotH = +(1-pH).toFixed(3);
    const pE_given_NotH = +(Math.random()*0.9).toFixed(3);
    const denom = +(pE_given_H*pH + pE_given_NotH*pNotH).toFixed(5);
    if(denom>0){
      const pH_given_E = +( (pE_given_H*pH)/denom ).toFixed(3);
      addExample(item,{input_values:{P_H:pH,P_E_given_H:pE_given_H,P_E_given_notH:pE_given_NotH}, output:`P(H|E) = ${pH_given_E}`});
    }
  }

  // INTEGRALS: definite polynomial, trig, exp, substitution-friendly
  if(tags.includes('integral') || /\\int|integral/.test(canon+instr)){
    // definite polynomial
    const a=0,b=2,n=3; // integrate x^n
    const val = (Math.pow(b,n+1)-Math.pow(a,n+1))/(n+1);
    addExample(item,{input_values:{a:a,b:b,n:n}, output:`\\int_{${a}}^{${b}} x^{${n}} \\ dx = ${val}`});
    // trig definite
    addExample(item,{input_values:{a:0,b:Math.PI, k:2}, output:`\\int_{0}^{\\pi} sin(2x) \\ dx = 0`});
    // exponential
    addExample(item,{input_values:{a:0,b:1,c:2}, output:`\\int_{0}^{1} e^{2x} \\ dx = ${(Math.exp(2)-1)/2}`});
    // indefinite simple
    addExample(item,{input_values:{}, output:`\\int x \\ dx = x^2/2 + C`});
  }

  // MODULO / CRYPTO: congruence computations, inverse mod, small RSA-like encrypt/decrypt example
  if(tags.includes('modulo') || tags.includes('mod') || /mod|\\pmod|congruence|\\equiv/.test(canon+instr)){
    // simple congruence
    const n = 11; const a = Math.floor(Math.random()*100);
    addExample(item,{input_values:{a:a,n:n}, output:`${a} \equiv ${((a%n)+n)%n} \pmod{${n}}`} );
    // multiplicative inverse mod prime p
    const p = 13; const x = 5; // inv 5 mod 13 = 8
    const inv = 8;
    addExample(item,{input_values:{x:x, p:p}, output:`${x}^{-1} \equiv ${inv} \pmod{${p}}`});
    // small RSA example (not secure) - public e=5,n=33 (3*11), m=7 -> c = m^e mod n
    const e=5, nn=33, m=7;
    const c = Math.pow(m,e)%nn;
    addExample(item,{input_values:{m:m,e:e,n:nn}, output:`c = ${c} (m^{e} \bmod n)`});
  }

  // DATABASE: attribute closure, candidate keys, functional dependency closure
  if(tags.includes('database') || tags.includes('fd') || /functional dependency|closure|attribute closure|candidate key/.test(canon+instr)){
    // attribute closure example: attrs ABC, FDs: A->B, B->C then A+ = ABC
    addExample(item,{input_values:{attributes:['A'], fds:["A->B","B->C"]}, output:`A+ = {A,B,C}`});
    // candidate key example
    addExample(item,{input_values:{attrs:['A','B','C'], fds:["A->D","B->E","C->F"]}, output:`Candidate keys include {A,B,C}`});
  }
}

fs.writeFileSync(p, JSON.stringify(data,null,2));
console.log('Domain examples added:', added);
