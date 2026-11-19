using SalesMobileApp.Core;
using SalesMobileApp.ViewModels;
namespace SalesMobileApp.Pages;
public partial class LoginPage : ContentPage
{
    private readonly LoginViewModel _vm;
    public LoginPage() { InitializeComponent(); _vm = new(ServiceLocator.Services.GetRequiredService<Services.ApiClient>(), ServiceLocator.Services.GetRequiredService<Services.SessionStore>()); BindingContext = _vm; _ = _vm.LoadSuggestedUrlAsync(); }
}
