using System.ComponentModel;
using System.Runtime.CompilerServices;
namespace SalesMobileApp.Core;
public abstract class ObservableObject : INotifyPropertyChanged
{
    public event PropertyChangedEventHandler? PropertyChanged;
    protected bool SetProperty<T>(ref T storage, T value, [CallerMemberName] string? name = null) { if (EqualityComparer<T>.Default.Equals(storage, value)) return false; storage = value; PropertyChanged?.Invoke(this, new(name)); return true; }
    protected void OnPropertyChanged([CallerMemberName] string? name = null) => PropertyChanged?.Invoke(this, new(name));
}
