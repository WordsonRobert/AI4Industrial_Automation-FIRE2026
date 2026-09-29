
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
        let mut speed_select: bool = false;
        let mut low_speed_set: i32 = 0;
        let mut high_speed_set: i32 = 0;
        let mut conveyor_speed: i32 = 0;
        let mut running_lamp: bool = false;
        let mut conveyor_stopped: bool = false;
        let mut speed_mode: bool = false;
        
        loop {
            start_button = self.client.read_coils(48, 1)[0];
            stop_button = self.client.read_coils(49, 1)[0];
            speed_select = self.client.read_coils(50, 1)[0];
            low_speed_set = self.client.read_holding_register(34);
            high_speed_set = self.client.read_holding_register(35);
            
            conveyor_stopped = (start_button || stop_button);
            if conveyor_stopped {
                speed_mode = false;
                conveyor_speed = 0;
                running_lamp = false;
            } else if (speed_select == true) {
                speed_mode = true;
                conveyor_speed = high_speed_set;
                running_lamp = true;
            }
            if speed_mode {
                conveyor_speed = low_speed_set;
            }
            
            self.client.write_register(34, conveyor_speed);
            self.client.write_coil(48, running_lamp);
            
            std::thread::sleep(std::time::Duration::from_millis(20));
        }
    }
}

fn main() {
    let mut program = PlcProgram::new();
    program.run();
}