using System.Collections.ObjectModel;
using SalesMobileApp.Core;
using SalesMobileApp.Models;
using SalesMobileApp.Services;
namespace SalesMobileApp.ViewModels;
public sealed class InvoiceViewModel : ObservableObject
{
    private readonly ApiClient _api; private readonly SessionStore _session; private ZoneDto? _selectedZone; private string _orders = "1", _amount = "", _customers = "1", _notes = "", _error = "", _message = ""; private bool _isBusy;
    public ObservableCollection<ZoneDto> Zones { get; } = []; public ZoneDto? SelectedZone { get => _selectedZone; set => SetProperty(ref _selectedZone, value); } public string Orders { get => _orders; set => SetProperty(ref _orders, value); } public string Amount { get => _amount; set => SetProperty(ref _amount, value); } public string Customers { get => _customers; set => SetProperty(ref _customers, value); } public string Notes { get => _notes; set => SetProperty(ref _notes, value); } public string Error { get => _error; private set => SetProperty(ref _error, value); } public string Message { get => _message; private set => SetProperty(ref _message, value); }
    public bool IsBusy { get => _isBusy; private set { SetProperty(ref _isBusy, value); SubmitCommand.RaiseCanExecuteChanged(); } } public AsyncCommand SubmitCommand { get; }
    public InvoiceViewModel(ApiClient api, SessionStore session) { _api = api; _session = session; SubmitCommand = new(SubmitAsync, () => !IsBusy); }
    public void SetZones(IEnumerable<ZoneDto> zones) { Zones.Clear(); foreach (var zone in zones) Zones.Add(zone); SelectedZone ??= Zones.FirstOrDefault(); }
    private async Task SubmitAsync()
    {
        Error = Message = ""; if (SelectedZone is null) { Error = "Chọn zone được giao."; return; } if (!int.TryParse(Orders, out var orders) || orders <= 0) { Error = "Số đơn phải lớn hơn 0."; return; } if (!double.TryParse(Amount, out var amount) || amount < 0) { Error = "Giá trị hóa đơn không hợp lệ."; return; } if (!int.TryParse(Customers, out var customers) || customers < 0) { Error = "Số khách hàng không hợp lệ."; return; }
        IsBusy = true; try { var id = await _session.GetUserIdAsync(); if (id is null) return; await _api.SubmitInvoiceAsync(id.Value, new(SelectedZone.id, orders, amount, customers, DateTime.UtcNow, null, null, Notes)); Message = "Đã ghi nhận hóa đơn."; Amount = Notes = ""; } catch (Exception ex) { Error = ex is HttpRequestException ? "Không thể lưu. Kiểm tra kết nối backend." : ex.Message; } finally { IsBusy = false; }
    }
}
