// Run with node tests/browser_audio.cjs; no microphone, network, or API.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const html = fs.readFileSync(path.join(__dirname, '../echo/monitor.html'), 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
new Function(script); // Parse the entire shipped script.
const sent = [];
const source = {connect() {return this;}, start() {this.started = true;}, stop() {this.onended();}};
const node = {connect() {return this;}, pan: {}, gain: {}};
const context = {
  audio: {on: true, sources: [], ctx: {state: 'running',
    createBufferSource: () => source, createStereoPanner: () => node,
    createGain: () => node, destination: {}}},
  ws: {readyState: 1, send: s => sent.push(JSON.parse(s))},
  pcmToBuffer: () => ({}), Math,
};
vm.createContext(context);
vm.runInContext(script.slice(script.indexOf('  function playPcm'), script.indexOf('  function downsample')), context);
context.playPcm({id: 7, pan: [1, 0], pcm: '', sr: 24000});
assert.equal(source.started, true);
assert.deepEqual(sent, [{type: 'play_started', id: 7}]);
source.onended();
assert.deepEqual(sent[1], {type: 'play_ended', id: 7});
context.audio.ctx.state = 'suspended';
context.playPcm({id: 8});
assert.deepEqual(sent[2], {type: 'play_error', id: 8});
console.log('Browser audio script: syntax, start/end acknowledgement, suspended-context failure passed');

context.audio.ctx.state = "running";
context.playPcm({id: 9, pan: [0.5, 0.5]});
context.stopPcm();
assert.deepEqual(sent.at(-1), {type: "play_error", id: 9});

// Playback-only startup must not request microphone permission.
(async () => {
  const labels = {};
  context.$ = id => labels[id] ||= {textContent: ''};
  context.audio.on = false;
  context.audio.ctx.resume = async () => {context.audio.ctx.state = 'running';};
  context.navigator = {mediaDevices: {getUserMedia() {throw Error('Microphone must stay off');}}};
  vm.runInContext(script.slice(script.indexOf('  async function soundOn'), script.indexOf('  async function audioOn')), context);
  await context.soundOn();
  assert.equal(context.audio.on, true);
  assert.equal(labels.sound.textContent, '声音：开');
  assert.deepEqual(sent.at(-1), {type: 'audio_ready'});
  console.log('Playback-only startup passed without microphone access');
})().catch(error => {console.error(error); process.exitCode = 1;});

// Clearing a provisional transcript must remove its row, even when nonempty.
const draft = {isConnected: true, removed: false, remove() {this.removed = true;},
  querySelector() {return {textContent: '并没有说出的临时识别…'};}};
const transcriptContext = {live: {'新朋友': draft}};
vm.createContext(transcriptContext);
vm.runInContext(script.slice(script.indexOf('  function onMessage'), script.indexOf('  function list(')), transcriptContext);
transcriptContext.onMessage({type: 'hearing', text: ''});
assert.equal(draft.removed, true);
assert.equal(transcriptContext.live['新朋友'], undefined);
console.log('Provisional transcript cleanup passed');
