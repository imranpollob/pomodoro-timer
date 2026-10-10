import type { Command, Snapshot } from './types';

export interface Transport {
  read(): Promise<Snapshot>;
  command(command: Command): Promise<Snapshot>;
  subscribe(callback: (state: Snapshot) => void): Promise<() => void>;
}

export class TimerClient {
  private revision = -1;
  private disposed = false;
  private unsubscribe?: () => void;
  constructor(private transport: Transport, private changed: (state: Snapshot) => void) {}
  private accept = (state: Snapshot) => {
    if (!this.disposed && state.revision >= this.revision) {
      this.revision = state.revision;
      this.changed(state);
    }
  };
  async start() {
    const unsubscribe = await this.transport.subscribe(this.accept);
    if (this.disposed) { unsubscribe(); return; }
    this.unsubscribe = unsubscribe;
    this.accept(await this.transport.read());
  }
  async send(command: Command) { this.accept(await this.transport.command(command)); }
  dispose() { this.disposed = true; this.unsubscribe?.(); }
}
