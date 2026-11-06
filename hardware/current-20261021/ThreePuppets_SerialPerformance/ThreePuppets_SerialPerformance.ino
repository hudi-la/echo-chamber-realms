#include <PuppetEyes.h>
#include <string.h>
#include <stdio.h>
PuppetEyes eyes;
char line[80];
byte used = 0;
bool overflowed = false, configured = false, activeLow = false;
unsigned long contact = 0, until[3] = {0,0,0};
// Existing hardware: mouse head servo on D10; dog remains relay-driven on D13.
const int HEAD_CENTER = 1500, HEAD_DOWN = 1550;
const unsigned long HALF_NOD_MS = 650;
unsigned long nodStarted = 0;
bool wasBusy[3] = {false,false,false};
const byte BODY_PINS[3] = {12, 255, 13};
void stopBodies() {
  for (byte p=0;p<3;p++) {
    until[p]=0;
    if (configured && p!=1) digitalWrite(BODY_PINS[p], activeLow ? HIGH : LOW);
  }
  eyes.head(1500);
}
void command(char *s) {
  int p,g,b,v,ms; char extra;
  contact=millis();
  if (!strcmp(s,"PING")) return;
  if (!strcmp(s,"STOP")) { stopBodies(); Serial.println("OK STOP"); return; }
  if (!strcmp(s,"CONFIG HIGH") || !strcmp(s,"CONFIG LOW")) {
    stopBodies(); activeLow=!strcmp(s,"CONFIG LOW"); configured=true;
    for (byte i=0;i<3;i+=2) {
      digitalWrite(BODY_PINS[i],activeLow ? HIGH : LOW);
      pinMode(BODY_PINS[i],OUTPUT);
    }
    Serial.println("OK CONFIG"); return;
  }
  if (sscanf(s,"LOOK %d %d %d %d %c",&p,&g,&b,&v,&extra)==4 && p>=0 && p<3 && g>=0 && g<9 && b>=0 && b<2 && v>=0 && v<2) {
    Serial.println(eyes.look((Puppet)p,(Gaze)g,(Blink)b,(Speed)v) ? "OK LOOK" : "BUSY DROP"); return;
  }
  if (sscanf(s,"BODY %d %d %c",&p,&ms,&extra)==2 && p>=0 && p<3 && ms>=0 && ms<=1200 && configured) {
    if (p==1) {
      if (ms && !until[1]) nodStarted=millis();
      if (!ms) eyes.head(HEAD_CENTER);
    }
    else digitalWrite(BODY_PINS[p], ms ? (activeLow ? LOW : HIGH) : (activeLow ? HIGH : LOW));
    until[p]=ms ? millis()+ms : 0;
    Serial.println("OK BODY"); return;
  }
  Serial.println("ERR COMMAND");
}
void setup() {
  Serial.begin(115200);
  // Installed relays: HIGH=on, LOW=off, verified against puppet_gpt_project.
  digitalWrite(12, LOW); pinMode(12, OUTPUT);
  digitalWrite(13, LOW); pinMode(13, OUTPUT);
  eyes.begin(); contact=millis(); Serial.println("READY ECR2");
}
void loop() {
  eyes.update();
  for(byte p=0;p<3;p++) {
    bool busy=eyes.isBusy((Puppet)p);
    if(wasBusy[p] && !busy) { Serial.print("IDLE "); Serial.println(p); }
    wasBusy[p]=busy;
  }
  unsigned long now=millis();
  if (now-contact>1800) stopBodies();
  for(byte p=0;p<3;p++) if(until[p] && (long)(now-until[p])>=0) {
    until[p]=0;
    if(p==1) eyes.head(1500);
    else if(configured) digitalWrite(BODY_PINS[p],activeLow ? HIGH : LOW);
  }
  if(until[1]) {
    unsigned long phase=(now-nodStarted) % (2*HALF_NOD_MS);
    unsigned long progress=phase<=HALF_NOD_MS ? phase : 2*HALF_NOD_MS-phase;
    eyes.head(HEAD_CENTER + (long)(HEAD_DOWN-HEAD_CENTER)*progress/HALF_NOD_MS);
  }
  while(Serial.available()) {
    char c=Serial.read();
    if(c=='\r') continue;
    if(c=='\n') {
      line[used]=0;
      if(!overflowed) command(line); else Serial.println("ERR OVERFLOW");
      used=0; overflowed=false;
    } else if(used<sizeof(line)-1 && !overflowed) line[used++]=c;
    else overflowed=true;
  }
}
