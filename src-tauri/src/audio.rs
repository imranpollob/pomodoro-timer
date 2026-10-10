//! Native audio remains independent of webview visibility and autoplay policy.
use rodio::{OutputStream, OutputStreamBuilder, Sink, Source, source::SineWave};
use std::{sync::mpsc, time::Duration};

enum Request {
    Play(u8, mpsc::Sender<Result<(), String>>),
    Stop,
}

#[derive(Clone)]
pub struct AudioService(mpsc::Sender<Request>);
impl AudioService {
    pub fn start() -> Result<Self, String> {
        let (sender, receiver) = mpsc::channel();
        std::thread::Builder::new()
            .name("focus-audio".into())
            .spawn(move || {
                let mut playing: Option<(OutputStream, Sink)> = None;
                loop {
                    match receiver.recv_timeout(Duration::from_millis(100)) {
                        Ok(Request::Play(volume, reply)) => {
                            // Replacing a preview cancels the previous tone, without stacking audio.
                            playing.take();
                            let result = OutputStreamBuilder::open_default_stream()
                                .map(|mut stream| {
                                    stream.log_on_drop(false);
                                    let sink = Sink::connect_new(stream.mixer());
                                    sink.set_volume(f32::from(volume) / 100.0);
                                    sink.append(
                                        SineWave::new(660.0)
                                            .take_duration(Duration::from_millis(350))
                                            .fade_in(Duration::from_millis(10))
                                            .amplify(0.15),
                                    );
                                    playing = Some((stream, sink));
                                })
                                .map_err(|e| {
                                    format!("Audio unavailable: {e}. Check your output device.")
                                });
                            let _ = reply.send(result);
                        }
                        Ok(Request::Stop) => {
                            playing.take();
                        }
                        Err(mpsc::RecvTimeoutError::Timeout) => {
                            if playing.as_ref().is_some_and(|(_, sink)| sink.empty()) {
                                playing.take();
                            }
                        }
                        Err(mpsc::RecvTimeoutError::Disconnected) => break,
                    }
                }
            })
            .map_err(|e| e.to_string())?;
        Ok(Self(sender))
    }
    pub fn play(&self, volume: u8) -> Result<(), String> {
        if volume > 100 {
            return Err("Volume must be from 0 to 100.".into());
        }
        if volume == 0 {
            self.stop();
            return Ok(());
        }
        let (send, receive) = mpsc::channel();
        self.0
            .send(Request::Play(volume, send))
            .map_err(|e| e.to_string())?;
        receive
            .recv_timeout(Duration::from_secs(5))
            .map_err(|e| e.to_string())?
    }
    pub fn stop(&self) {
        let _ = self.0.send(Request::Stop);
    }
}
