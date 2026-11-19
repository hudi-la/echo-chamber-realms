const assert=require('node:assert/strict');
const sentences=require('../echo/static/text-sentences.js');
assert.deepEqual(sentences('They noticed his answer first. I wish that did not matter so much to me.'),['They noticed his answer first.','I wish that did not matter so much to me.']);
assert.deepEqual(sentences('我想先说完。你可以等一下吗？'),['我想先说完。','你可以等一下吗？']);
const line='I wanted to help, but I think I was trying to prove that they still need me.';
assert.deepEqual(sentences(line),[line]);
assert.deepEqual(sentences(''),[]);
assert.equal(sentences('Mr. Smith is here.').join(' '),'Mr. Smith is here.');
console.log('Whole sentences preserve punctuation, spaces, word order, and Chinese/English boundaries.');
