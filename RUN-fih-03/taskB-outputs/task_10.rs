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
        let mut car_present: bool = false;
        let mut start_button: bool = false;
        let mut wash_pump: bool = false;
        let mut rinse_valve: bool = false;
        let mut dryer_fan: bool = false;
        let mut cycle_complete: bool = false;
        let mut ton_wash_acc: u64 = 0;
        let mut ton_wash_q: bool = false;
        let mut ton_rinse_acc: u64 = 0;
        let mut ton_rinse_q: bool = false;
        let mut ton_dry_acc: u64 = 0;
        let mut ton_dry_q: bool = false;
        
        loop {
            car_present = self.client.read_coils(72, 1)[0];
            start_button = self.client.read_coils(73, 1)[0];
            
            wash_pump = false;
            rinse_valve = false;
            dryer_fan = false;
            cycle_complete = false;
            if (car_present && start_button) {
                if true { ton_wash_acc += 1; } else { ton_wash_acc = 0; }
                ton_wash_q = ton_wash_acc >= 1000;
            } else if ton_wash_q {
                if true { ton_rinse_acc += 1; } else { ton_rinse_acc = 0; }
                ton_rinse_q = ton_rinse_acc >= 750;
            } else if ton_rinse_q {
                if true { ton_dry_acc += 1; } else { ton_dry_acc = 0; }
                ton_dry_q = ton_dry_acc >= 500;
            } else if ton_dry_q {
                cycle_complete = true;
            }
            
            self.client.write_coil(72, wash_pump);
            self.client.write_coil(73, rinse_valve);
            self.client.write_coil(74, dryer_fan);
            self.client.write_coil(75, cycle_complete);
            
            std::thread::sleep(std::time::Duration::from_millis(20));
        }
    }
}

fn main() {
    let mut program = PlcProgram::new();
    program.run();
}