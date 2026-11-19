#include <cassert>
#include <iostream>
#include "PuppetEyes.h"
#ifndef ECR_DOG_YAW_ENABLED
#define ECR_DOG_YAW_ENABLED 0
#endif
unsigned long fakeMillis=0;
int pulse[20]={0};
int main(){
 const int expect[3][9][2]={
 {{1500,1500},{1930,1500},{1070,1500},{1500,2120},{1500,1170},{1880,2050},{1120,2050},{1880,1205},{1120,1205}},
 {{1500,1500},{1310,1500},{1640,1500},{1500,1500},{1500,1500},{1330,1500},{1630,1500},{1330,1500},{1630,1500}},
 {{1500,1500},{1930,1500},{1025,1500},{1500,1830},{1500,1120},{1880,1800},{1075,1800},{1880,1160},{1075,1160}}};
 const int yawPins[]={3,8,7}, pitchPins[]={2,-1,6};
 for(int p=0;p<3;p++)for(int g=0;g<9;g++)for(int smooth=0;smooth<2;smooth++){
  PuppetEyes eyes;eyes.begin();
  assert(eyes.look((Puppet)p,(Gaze)g,Blink::Yes,smooth?Speed::Smooth:Speed::Fast));
  for(int i=0;i<800 && eyes.isBusy();i++){fakeMillis+=5;eyes.update();}
  assert(!eyes.isBusy());
  if(p!=2 || ECR_DOG_YAW_ENABLED) assert(pulse[yawPins[p]]==expect[p][g][0]);
  else assert(pulse[7]==0);
  if(pitchPins[p]>=0)assert(pulse[pitchPins[p]]==expect[p][g][1]);
 }
 const int lo[]={855,980,1170,1070,930,880,1120,1025,1310,1450,1500};
 const int hi[]={2020,2220,2120,1930,2165,2090,1830,1930,1640,1970,1500};
 const int pins[]={14,15,2,3,4,5,6,7,8,9,10};
 // Exercise every ordered transition, including blinking while already looking up.
 for(int p=0;p<3;p++)for(int from=0;from<9;from++)for(int to=0;to<9;to++)
 for(int smooth=0;smooth<2;smooth++)for(int blink=0;blink<2;blink++){
  PuppetEyes eyes;eyes.begin();
  assert(eyes.look((Puppet)p,(Gaze)from,Blink::No,Speed::Fast));
  for(int i=0;i<800 && eyes.isBusy();i++){fakeMillis+=5;eyes.update();}
  assert(eyes.look((Puppet)p,(Gaze)to,blink?Blink::Yes:Blink::No,
                   smooth?Speed::Smooth:Speed::Fast));
  for(int i=0;i<800;i++){
   for(int j=0;j<11;j++){
    if(j==7 && !ECR_DOG_YAW_ENABLED)assert(pulse[7]==0);
    else assert(pulse[pins[j]]>=lo[j] && pulse[pins[j]]<=hi[j]);
   }
   // Raised eyeballs must retain the new open-lid targets, not rest/closed targets.
   if(pulse[2]>1500){assert(pulse[14]==855);assert(pulse[15]==2220);}
   if(pulse[6]>1500){assert(pulse[4]==930);assert(pulse[5]==2090);}
   if(!eyes.isBusy())break;
   fakeMillis+=5;eyes.update();
  }
  assert(!eyes.isBusy());
  if(p!=2 || ECR_DOG_YAW_ENABLED) assert(pulse[yawPins[p]]==expect[p][to][0]);
  else assert(pulse[7]==0);
  if(pitchPins[p]>=0)assert(pulse[pitchPins[p]]==expect[p][to][1]);
 }
 std::cout<<"54 gaze cases and 972 transitions passed, including pulse bounds and raised-eye lid coordination.\n";
}
