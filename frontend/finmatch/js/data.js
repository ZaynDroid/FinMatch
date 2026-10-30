/* Demo data. Fake logins live here (demo only, never real passwords). */
const DEMO={user:{id:'user@finmatch.demo',mobile:'9876543210',pw:'demo123'},admin:{id:'admin@finmatch.demo',pw:'admin123'}};
const MONTHS=['May','Jun','Jul','Aug','Sep','Oct'];
const BILLED=[210000,245000,198000,260000,275000,320000],RECEIVED=[180000,220000,185000,230000,240000,200000];
const NEWBIZ=[2,3,1,4,3,5];
const inv=(id,cust,amt,date,due,phone)=>({id,cust,amt,date,due,ref:'B-'+(2100+ +id.slice(4)),phone,note:'',edited:'',hist:[]});
const SEED={
 invoices:[
  inv('INV-101','Sharma Kirana Store',12500,'2026-10-05','2026-10-20','9876500001'),
  inv('INV-102','Gupta Hardware',48000,'2026-10-06','2026-10-25','9876500002'),
  inv('INV-103','Verma Medical Hall',7800,'2026-10-08','2026-11-05','9876500003'),
  inv('INV-104','Singh Tuition Centre',15000,'2026-10-01','2026-10-15','9876500004'),
  inv('INV-105','Rawat Wholesale Traders',125000,'2026-10-10','2026-10-28','9876500005'),
  inv('INV-106','Joshi Dairy',6800,'2026-10-12','2026-11-10','9876500006'),
  inv('INV-107','Bisht Clinic',9600,'2026-10-03','2026-10-18','9876500007'),
  inv('INV-108','Negi Electricals',22400,'2026-10-15','2026-11-02','9876500008'),
  inv('INV-109','Pant Cloth House',56000,'2026-09-28','2026-10-12','9876500009'),
  inv('INV-110','Kumar Sweets',4500,'2026-10-18','2026-11-08','9876500010'),
  inv('INV-111','Arora Auto Parts',31000,'2026-10-02','2026-10-22','9876500011'),
  inv('INV-112','Sharma Kirana Store',6800,'2026-10-22','2026-11-12','9876500001')],
 payments:[
  {id:'PAY-501',from:'Sharma Kirana',amt:12500,date:'2026-10-07',mode:'UPI',ref:'UPI4382910'},
  {id:'PAY-502',from:'Gupta Hardware',amt:30000,date:'2026-10-14',mode:'Bank Transfer',ref:'NEFT771204'},
  {id:'PAY-503',from:'Verma Medical',amt:7800,date:'2026-10-16',mode:'UPI',ref:'UPI5521097'},
  {id:'PAY-504',from:'Singh Tuition',amt:15000,date:'2026-10-12',mode:'Cash',ref:'CASH-0412'},
  {id:'PAY-505',from:'Rawat Wholesale',amt:60000,date:'2026-10-18',mode:'Cheque',ref:'CHQ000341'},
  {id:'PAY-506',from:'Joshi Dairy',amt:6800,date:'2026-10-20',mode:'UPI',ref:'UPI6610342'},
  {id:'PAY-507',from:'Dr Bisht',amt:9600,date:'2026-10-17',mode:'UPI',ref:'UPI7712009'},
  {id:'PAY-508',from:'Negi Elec',amt:10000,date:'2026-10-22',mode:'UPI',ref:'UPI8820451'},
  {id:'PAY-509',from:'Kumar Sweets',amt:4500,date:'2026-10-25',mode:'Cash',ref:'CASH-0425'},
  {id:'PAY-510',from:'Ramesh',amt:6800,date:'2026-10-26',mode:'UPI',ref:'UPI9930118'}],
 matches:[
  {id:'M1',inv:'INV-101',pay:'PAY-501',score:96,reason:'Naam milta hai, amount same hai, 2 din baad aaya',status:'approved'},
  {id:'M2',inv:'INV-102',pay:'PAY-502',score:70,reason:'Naam milta hai, par amount kam hai',status:'suggested'},
  {id:'M3',inv:'INV-103',pay:'PAY-503',score:98,reason:'Naam milta hai, amount same hai',status:'approved'},
  {id:'M4',inv:'INV-104',pay:'PAY-504',score:88,reason:'Naam milta hai, amount same hai (cash)',status:'approved'},
  {id:'M5',inv:'INV-105',pay:'PAY-505',score:82,reason:'Naam milta hai, aadha paisa aaya',status:'approved'},
  {id:'M6',inv:'INV-106',pay:'PAY-506',score:85,reason:'Naam milta hai, amount same hai',status:'suggested'},
  {id:'M7',inv:'INV-107',pay:'PAY-507',score:60,reason:'Amount same hai, naam thoda alag hai (Dr Bisht)',status:'suggested'},
  {id:'M8',inv:'INV-108',pay:'PAY-508',score:55,reason:'Naam milta hai, amount kam hai',status:'suggested'},
  {id:'M9',inv:'INV-110',pay:'PAY-509',score:92,reason:'Naam milta hai, amount same hai',status:'approved'},
  {id:'M10',inv:'INV-112',pay:'PAY-510',score:62,reason:'Amount same hai, naam nahi mila',status:'suggested'},
  {id:'M11',inv:'INV-106',pay:'PAY-510',score:58,reason:'Amount same hai, naam nahi mila',status:'suggested'}],
 businesses:[
  {id:'B1',name:'Sharma Traders',owner:'Rajesh Sharma',town:'Haldwani',mobile:'9876543210',joined:'2026-05-12',status:'Active',files:14},
  {id:'B2',name:'Gupta Hardware',owner:'Anil Gupta',town:'Rudrapur',mobile:'9811100002',joined:'2026-06-03',status:'Active',files:9},
  {id:'B3',name:'Verma Medical Hall',owner:'Sunita Verma',town:'Kashipur',mobile:'9811100003',joined:'2026-07-19',status:'Active',files:6},
  {id:'B4',name:'Rawat Wholesale',owner:'Mohan Rawat',town:'Kotdwar',mobile:'9811100004',joined:'2026-08-08',status:'Disabled',files:2},
  {id:'B5',name:'Joshi Tuition Centre',owner:'Meena Joshi',town:'Almora',mobile:'9811100005',joined:'2026-09-14',status:'Active',files:5},
  {id:'B6',name:'Negi Electricals',owner:'Dinesh Negi',town:'Pithoragarh',mobile:'9811100006',joined:'2026-10-02',status:'Active',files:3}],
 support:[
  {id:'R1',name:'Rajesh Sharma',biz:'Sharma Traders',topic:'Upload problem',msg:'CSV upload mein error aa raha hai.',date:'2026-10-27',status:'Open'},
  {id:'R2',name:'Anil Gupta',biz:'Gupta Hardware',topic:'Payment amount',msg:'Payment ka amount galat dikh raha hai, kaise theek karein?',date:'2026-10-25',status:'Open'},
  {id:'R3',name:'Sunita Verma',biz:'Verma Medical Hall',topic:'Hindi language',msg:'Hindi mein sab kuch dikhana hai.',date:'2026-10-20',status:'Resolved'}]
};
