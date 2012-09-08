/*
Control iBoom
Protocol, Serial (COM Port, e.g., COM3), each command ends with \n
Commands:
1. gon - turn on Green laser 
2. goff - turn off Green laser
 3 s - shoot CO/2 laser
 4 shotLength=xxx, sets CO/2 shooting length to xxx ms, xxx is forced to be beteeen thresholds, e.g., shotLength=1000 sets the shooting period per "s" command to 1 second

 */
 
// Pin 13 has an LED connected on most Arduino boards.
// give it a name:
int led = 11;
int greenLaser=4;
int shotLength=200;
String inputString = "";         // a string to hold incoming data
String numString ="";
boolean stringComplete = false;  // whether the string is complete
boolean bufferEmptied=false;
char buffer[200];

// the setup routine runs once when you press reset:
void setup() {                
  // initialize the digital pin as an output.
  pinMode(led, OUTPUT);     
  digitalWrite(led, LOW);    // turn the LED off by making the voltage LOW
  digitalWrite(greenLaser,LOW);
  // initialize serial:
  Serial.begin(9600);
  // reserve 200 bytes for the inputString:
  inputString.reserve(200);
  numString.reserve(200);
}

// the loop routine runs over and over again forever:
void loop() {
  // print the string when a newline arrives:
  if (!stringComplete)
  return;
    inputString.trim();
    Serial.println(inputString); 
    if (inputString.startsWith("shotLength=") ) {
         String subStr =  inputString.substring(11);
        Serial.print("Substring=");
        Serial.print(subStr);
        Serial.println("#");
        subStr.toCharArray(buffer,200);
        shotLength=atoi(buffer);
        if (shotLength>3000)
            shotLength=3000;
         if (shotLength<10)
           shotLength=10;
             Serial.print("ShotLength Set to ");
     Serial.print(shotLength);
      Serial.println("");
    } else
     if (inputString == "s")  {
       digitalWrite(led, HIGH);   // turn the LED on (HIGH is the voltage level)
  delay(shotLength);               // wait for a second
  digitalWrite(led, LOW);    // turn the LED off by making the voltage LOW
  Serial.print("DoneShot ");
  Serial.print(shotLength);
  Serial.println("ms");
    } else if (inputString=="gon" ) {
        digitalWrite(greenLaser,HIGH);
    } else if (inputString=="goff") {
      digitalWrite(greenLaser,LOW);
    } else{
    Serial.print("Unknown Command:");
    Serial.print(inputString);
  }
  // clear the string:
     inputString = "";
    stringComplete = false;
    //empty buffer
                      while(Serial.available())
                       Serial.read();
    
 }
 
 /*
  SerialEvent occurs whenever a new data comes in the
 hardware serial RX.  This routine is run between each
 time loop() runs, so using delay inside loop can delay
 response.  Multiple bytes of data may be available.
 */
void serialEvent() {
//  if (Serial.available() == 0 )
//        bufferEmptied = true;
//    else {
//              if (!bufferEmptied) {
   //                       Serial.println("emptying Serial"); 
//                   while(Serial.available())
//                       Serial.read();
//                       bufferEmptied = true;
//              } else
              while (Serial.available()) {
                // get the new byte:
                char inChar = (char)Serial.read(); 
              // add it to the inputString:
                inputString += inChar;
                // if the incoming character is a newline, set a flag
                // so the main loop can do something about it:
                if (inChar == '\n') {
                  stringComplete = true;
                  bufferEmptied = false;
                } 
   //           }
     }
}
