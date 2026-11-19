/* Keep complete sentences, punctuation, spaces and word order. Never turn words into a glyph bag. */
(function(root){
  'use strict';
  function sentences(text){
    text=String(text||'').trim();if(!text)return [];
    if(typeof Intl!=='undefined'&&Intl.Segmenter){
      return Array.from(new Intl.Segmenter(undefined,{granularity:'sentence'}).segment(text),s=>s.segment.trim()).filter(Boolean);
    }
    return (text.match(/[^。！？.!?\n]+(?:[。！？.!?]+[”’"']*|$)/gu)||[text]).map(s=>s.trim()).filter(Boolean);
  }
  if(typeof module!=='undefined'&&module.exports)module.exports=sentences;else root.TextSentences=sentences;
})(typeof window==='undefined'?{}:window);
