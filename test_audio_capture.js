const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
const source = audioCtx.createMediaElementSource(html5Vid);
const dest = audioCtx.createMediaStreamDestination();
source.connect(dest);
source.connect(audioCtx.destination); // So the user can still hear it
const audioStream = dest.stream;
// audioStream now has the audio track!
