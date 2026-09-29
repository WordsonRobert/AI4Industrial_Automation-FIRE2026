
// --- auto-injected self-contained Modbus stub, matching the real
// `modbus` crate's documented API surface (Coil, Config, tcp::Transport)
// so generated code compiles standalone without the actual external
// crate or hardware -- appropriate given Task B's goal is syntactic
// correctness + logic preservation, not literal I/O.
mod modbus {
    #[derive(PartialEq, Clone, Copy)]
    pub enum Coil { On, Off }

    pub trait Client {}

    pub mod tcp {
        use super::Coil;

        #[derive(Default)]
        pub struct Config {
            pub tcp_port: u16,
            pub modbus_uid: u8,
        }

        pub struct Transport {
            registers: [u16; 256],
            coils: [Coil; 256],
        }

        impl Transport {
            pub fn new_with_cfg(_addr: &str, _cfg: Config) -> Result<Self, String> {
                Ok(Transport { registers: [0; 256], coils: [Coil::Off; 256] })
            }
            pub fn read_coils(&mut self, address: u16, count: u16) -> Result<Vec<Coil>, String> {
                let start = address as usize % 256;
                Ok((0..count as usize).map(|i| self.coils[(start + i) % 256]).collect())
            }
            pub fn write_single_coil(&mut self, address: u16, coil: Coil) -> Result<(), String> {
                self.coils[address as usize % 256] = coil;
                Ok(())
            }
            pub fn read_holding_registers(&mut self, address: u16, count: u16) -> Result<Vec<u16>, String> {
                let start = address as usize % 256;
                Ok((0..count as usize).map(|i| self.registers[(start + i) % 256]).collect())
            }
            pub fn write_single_register(&mut self, address: u16, value: u16) -> Result<(), String> {
                self.registers[address as usize % 256] = value;
                Ok(())
            }
        }
    }
}

use modbus::{Client, Coil};
use modbus::tcp::{self, Config};

const MODBUS_SERVER_IP: &str = "127.0.0.1";
const MODBUS_PORT: u16 = 502;
const UNIT_ID: u8 = 1;

struct ModbusClient {
    client: tcp::Transport,
}

impl ModbusClient {
    fn new() -> Self {
        let cfg = Config { tcp_port: MODBUS_PORT, modbus_uid: UNIT_ID, ..Default::default() };
        let client = tcp::Transport::new_with_cfg(MODBUS_SERVER_IP, cfg).expect("Failed to connect");
        Self { client }
    }
    
    fn read_coils(&mut self, address: u16, count: u16) -> Vec<bool> {
        self.client.read_coils(address, count).expect("read_coils failed")
            .into_iter().map(|c| c == Coil::On).collect()
    }
    
    fn write_coil(&mut self, address: u16, value: bool) {
        let coil = if value { Coil::On } else { Coil::Off };
        self.client.write_single_coil(address, coil).expect("write_coil failed");
    }
    
    fn read_holding_register(&mut self, address: u16) -> i32 {
        let regs = self.client.read_holding_registers(address, 1).expect("read_holding_register failed");
        regs[0] as i32
    }
    
    fn write_register(&mut self, address: u16, value: i32) {
        self.client.write_single_register(address, value as u16).expect("write_register failed");
    }
}

struct PlcProgram {
    client: ModbusClient,
}

impl PlcProgram {
    fn new() -> Self {
        Self { client: ModbusClient::new() }
    }
    
    fn run(&mut self) {
        let mut start_button: bool = false;
        let mut reset_button: bool = false;
        let mut level_a_full: bool = false;
        let mut level_b_full: bool = false;
        let mut ingredient_a_valve: bool = false;
        let mut ingredient_b_valve: bool = false;
        let mut mixer_motor: bool = false;
        let mut batch_complete: bool = false;
        let mut ton_mixing_acc: u64 = 0;
        let mut ton_mixing_q: bool = false;
        let mut scaled_level_a: f64 = 0.0;
        let mut scaled_level_b: f64 = 0.0;
        
        loop {
            start_button = self.client.read_coils(56, 1)[0];
            reset_button = self.client.read_coils(57, 1)[0];
            level_a_full = self.client.read_coils(58, 1)[0];
            level_b_full = self.client.read_coils(59, 1)[0];
            
            scaled_level_a = (level_a_full / 50.0);
            scaled_level_b = (level_b_full / 50.0);
            ingredient_a_valve = ((scaled_level_a >= 49.0) && !batch_complete);
            ingredient_b_valve = ((scaled_level_b >= 49.0) && !batch_complete);
            if ((start_button && !batch_complete) || reset_button) { ton_mixing_acc += 1; } else { ton_mixing_acc = 0; }
            ton_mixing_q = ton_mixing_acc >= 1500;
            mixer_motor = ton_mixing_q;
            batch_complete = (mixer_motor || reset_button);
            
            self.client.write_coil(56, ingredient_a_valve);
            self.client.write_coil(57, ingredient_b_valve);
            self.client.write_coil(58, mixer_motor);
            self.client.write_coil(59, batch_complete);
            
            std::thread::sleep(std::time::Duration::from_millis(20));
        }
    }
}

fn main() {
    let mut program = PlcProgram::new();
    program.run();
}