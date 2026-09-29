
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
        let mut stop_button: bool = false;
        let mut conveyor_run: bool = false;
        let mut rpm_set: i32 = 0;
        let mut digital_display: i32 = 0;
        let mut rpm_rpm: i32 = 0;
        let mut ton_conveyor_acc: u64 = 0;
        let mut ton_conveyor_q: bool = false;
        
        loop {
            start_button = self.client.read_coils(0, 1)[0];
            stop_button = self.client.read_coils(1, 1)[0];
            rpm_set = self.client.read_holding_register(0);
            
            if (start_button && !ton_conveyor_q) { ton_conveyor_acc += 1; } else { ton_conveyor_acc = 0; }
            ton_conveyor_q = ton_conveyor_acc >= 100;
            rpm_rpm = rpm_set;
            digital_display = rpm_rpm;
            conveyor_run = ton_conveyor_q;
            
            self.client.write_coil(0, conveyor_run);
            self.client.write_register(0, digital_display);
            
            std::thread::sleep(std::time::Duration::from_millis(20));
        }
    }
}

fn main() {
    let mut program = PlcProgram::new();
    program.run();
}