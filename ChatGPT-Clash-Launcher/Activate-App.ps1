if (-not ('ClashLauncher.Activator' -as [type])) {
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
namespace ClashLauncher {
 [ComImport, Guid("2e941141-7f97-4756-ba1d-9decde894a3d"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
 interface IActivation {
  [PreserveSig] int ActivateApplication([MarshalAs(UnmanagedType.LPWStr)] string id,[MarshalAs(UnmanagedType.LPWStr)] string args,uint options,out uint pid);
  [PreserveSig] int ActivateForFile(IntPtr a,IntPtr b,IntPtr c,out uint pid);
  [PreserveSig] int ActivateForProtocol(IntPtr a,IntPtr b,out uint pid);
 }
 public static class Activator {
  public static uint Launch(string id,string args) {
   object obj=System.Activator.CreateInstance(Type.GetTypeFromCLSID(new Guid("45BA127D-10A8-46EA-8AB7-56EA9078943C")));
   try {uint pid; int hr=((IActivation)obj).ActivateApplication(id,args,0,out pid); if(hr<0) Marshal.ThrowExceptionForHR(hr); return pid;}
   finally {Marshal.ReleaseComObject(obj);}
  }
 }
}
'@
}
